"""THE NORTHERN GULF AND THE LEVANT -- Iraq, Iran, Jordan, Lebanon and Syria as FIVE MACHINES.

WHY ONE PACK AND NOT FIVE, AND WHY NOT A FOOTNOTE TO THE GULF. The desk already holds `gulf`
(Qatar, Kuwait, Oman, Bahrain), `sa` and `ae`. Those are dollar-pegged energy exporters with
sovereign wealth and working statistics. THIS pack answers for the five states along the top of
the Gulf and down the Levant, and not one of them is that shape:

  1. IRAQ IS OPEC'S SECOND-LARGEST PRODUCER (~4.2 mb/d) AND IT PUBLISHES ON A CLOCK. SOMO
     announces the Basrah Medium and Basrah Heavy Official Selling Prices on a dated monthly
     cycle; the Oil Ministry prints monthly export volumes AND revenues; and Iraq's repeated
     over-production against its OPEC+ quota has produced PUBLISHED COMPENSATION SCHEDULES --
     dated commitments to under-produce by named volumes in named months, against which
     compliance is measurable. Almost no other producer hands a desk that object.
  2. THE KURDISTAN-CEYHAN PIPELINE HAS BEEN SHUT SINCE 25 MARCH 2023. An ICC arbitration award
     against Turkey removed roughly 450 kb/d from the market on a dated, published legal ruling,
     and the restart negotiations have been public throughout. A supply shock with a COURT DATE
     on it is as clean a natural experiment as this market offers, and it is the single best
     reason this pack exists.
  3. IRAN HOLDS THE WORLD'S SECOND-LARGEST GAS RESERVES AND RUNS UNDER SANCTIONS, so its output
     is a function of PUBLISHED US ADMINISTRATIVE ACTS on dated days -- the 2015 JCPOA, the
     2018-05-08 withdrawal, the 2019-05-02 waiver expiries, the enforcement changes since. And
     OPEC prints Iranian production in TWO SERIES THAT DISAGREE (direct communication and
     secondary sources); the GAP between them is itself an observable with a monthly clock.
  4. THE IRANIAN HOUSEHOLD PRICES ITS OWN INFLATION IN GOLD, IN PUBLIC. The rial has an official
     rate and a free-market rate an order of magnitude apart, and the Bahar Azadi coin trades at
     a published PREMIUM to its own metal content. That premium is a domestic
     inflation-expectation gauge that is genuinely price-relevant to regional XAUUSD demand, and
     it is quoted every day in Persian.
  5. LEBANON IS THE MOST COMPLETE SOVEREIGN AND BANKING COLLAPSE OF THE CENTURY AND EVERY STAGE
     IS DATED: the 2019-10-17 protests, the 2020-03-07 eurobond default, Sayrafa and the
     banknote rate, the 2020-08-04 port explosion that destroyed the country's grain silos, and
     the official rate's move from 1,507.5 to 15,000 and then to 89,500. A peg that held for 22
     years and then failed completely, with every step published, is the desk's best available
     case study in peg failure. `dk` -- the Danish peg that has never failed -- is its natural
     control and is named in INTERACTIONS for exactly that reason.
  6. JORDAN IS THE CONTROL NEXT DOOR. A HARD PEG AT 0.709 JOD/USD held since 1995, through the
     2003 invasion, the 2011 uprisings, the Syrian war, two refugee waves and the 2019-2023
     Lebanese collapse, under a standing IMF programme. A peg that holds next door to a peg that
     collapsed, in the same region and the same decade, is an identification strategy rather
     than an anecdote. Jordan also owns the Dead Sea potash and phosphate industry, which routes
     into the fertiliser-cost chain and therefore into CORN and WHEAT.
  7. SYRIA IS THE HONEST LIMIT CASE, and the 2024-12-08 transition is a dated boundary that
     changes what data exists at all. Its published statistics largely stopped; its pound has
     several rates; its wheat imports, its phosphate and its Mediterranean position are visible
     mainly in MIRROR CUSTOMS DATA and UN agency reporting. Five source layers are DECLARED
     ABSENT for Syria by name, each with the lawful substitute that carries the information
     instead. A measured refusal with a named substitute beats a padded source list (L1.28a).

WHAT IS EXECUTABLE AND WHAT IS NOT. IQD, IRR, JOD, LBP and SYP are ALL ABSENT from
`data/universe/universe.json`, as are the four exchanges' indices, the Basrah and Iranian crude
grades, the potash and phosphate contracts and every local interbank rate. Each is in
`TRANSMISSION_TARGETS` with its regime -- OFFICIAL AND PARALLEL where two exist -- and the broker
symbols its economics reach, so an absent instrument mints a transmission hypothesis and never a
cell that can never be filled (L1.49). Crude, gas, gold, silver, the grain and soft complex, the
three lira legs, the two shekel legs and the three index legs are what the box can trade.

THE TWO-LANE ORDER (2026-09-06) IS LOUD HERE. SOMO, NIOC, Arab Potash, JPMC, Banque du Liban's
counterparties, the Iraqi and Jordanian banks and the Iranian bourse's names are what this ground
talks about, and every one of them is an EVENT-lane instrument. They appear below as ACTORS and
as TERMINOLOGY so an Arabic-, Persian- or Kurdish-language miner recognises the words. Not one is
a symbol in any instrument tuple.

NO CRYPTO-EXCHANGE GROUND IS HUNTED (mandate 2026-08-18). That refusal matters in a sanctions
pack, because the loudest crypto story in this region is sanctions evasion. Broker crypto CFDs
stay inside the MT5 universe; no venue, order book or exchange feed is named as a source
anywhere below, and no sanctioned counterparty's systems are touched by anything here.

EVERYTHING HERE IS PUBLIC AND LAWFUL -- see `ACCESS_CONSTRAINTS`, which says it in full.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "OPEC_NORTH"
NAME = "The Northern Gulf and Levant (Iraq, Iran, Jordan, Lebanon, Syria)"
REGION_COMMAND = "mea"             # the framework's command; the forest is mena
REGION_DESK = "MENA"
FOREST = "mena"
CURRENCY = "IQD"                   # the pack's nominal currency; the other four are below
#: THE FIVE ISO-2 CODES THIS PACK ANSWERS FOR. `check_regional_parity.jurisdictions_of` reads
#: this tuple and nothing else: a multi-country pack that declares nothing is credited with ONE
#: country, which would leave four of the parity fence's unanswered rows unanswered while the
#: work sat on disk.
JURISDICTIONS: tuple[str, ...] = ("iq", "ir", "jo", "lb", "sy")

#: THE FIVE CURRENCIES AND THEIR REGIMES. Three of the five have TWO OR MORE SIMULTANEOUS RATES,
#: which is the single most important fact in this file: a study that reads "the exchange rate"
#: of Iraq, Iran, Lebanon or Syria without saying WHICH rate is measuring a different instrument
#: from one month to the next. `official` is the administered parity, `parallel` the market rate
#: where one is published, and `since` the date the current arrangement took effect. NONE of the
#: five is quoted by this broker -- see TRANSMISSION_TARGETS.
CURRENCIES: dict[str, dict[str, Any]] = {
    "IQD": {"jurisdiction": "iq", "name": "Iraqi dinar (الدينار العراقي)",
            "regime": "administered_usd_rate_with_parallel_market",
            "official": 1320.0, "parallel": "published daily by the Baghdad and Erbil exchange "
                                            "markets; the PREMIUM over the official rate is the "
                                            "observable",
            "since": "2023-02-07",
            "authority": "Central Bank of Iraq (البنك المركزي العراقي)",
            "fact": "the CBI sells dollars through a daily auction and, since 2023, through a "
                    "compliance PLATFORM that routes transfers for prior screening. The official "
                    "rate was revalued from 1,460 to 1,320 on 2023-02-07 by decision of the "
                    "Council of Ministers; the PARALLEL rate did not follow, and the gap between "
                    "them widened sharply as US Treasury restrictions on dollar transfers "
                    "through the CBI tightened through 2023. A DATED ADMINISTRATIVE ACT WITH A "
                    "PUBLISHED, MEASURABLE CURRENCY EFFECT is the rarest object in FX research"},
    "IRR": {"jurisdiction": "ir", "name": "Iranian rial (ریال ایران)",
            "regime": "multiple_rates_official_and_free_market",
            "official": 42000.0, "parallel": "the free market (بازار آزاد) rate quoted daily in "
                                             "Tehran and reported by the domestic financial "
                                             "press; an ORDER OF MAGNITUDE weaker than official",
            "since": "2018-04-10",
            "authority": "Central Bank of Iran / Bank Markazi (بانک مرکزی ایران)",
            "fact": "the 42,000 'preferential' rate was decreed in April 2018 for essential "
                    "imports and has never been the market's price. Between it and the free "
                    "market sit the NIMA/ETS integrated-market rates for exporters. So Iran does "
                    "not have AN exchange rate: it has a lattice of them, each with its own "
                    "eligibility rule, and a claim about 'the rial' must name which"},
    "JOD": {"jurisdiction": "jo", "name": "Jordanian dinar (الدينار الأردني)",
            "regime": "hard_usd_peg", "official": 0.7090,
            "parallel": "none: the official and market rates are the same number, which is the "
                        "whole point of naming Jordan the control",
            "since": "1995-10-23",
            "authority": "Central Bank of Jordan (البنك المركزي الأردني)",
            "fact": "0.7090 dinars to the dollar, held since October 1995 through the 2003 "
                    "invasion, the 2011 uprisings, the Syrian war, two refugee waves, the "
                    "2014-2016 oil collapse and the 2019-2023 Lebanese collapse next door. THE "
                    "PEG THAT DID NOT FAIL, in the same region and the same decade as the peg "
                    "that did, under a standing IMF Extended Fund Facility"},
    "LBP": {"jurisdiction": "lb", "name": "Lebanese pound / lira (الليرة اللبنانية)",
            "regime": "failed_peg_multiple_rates", "official": 89500.0,
            "parallel": "the banknote market rate, the Sayrafa platform rate (2021-2023) and the "
                        "bank-deposit 'lollar' rate were three different prices for one currency "
                        "at the same moment",
            "since": "2023-11-01",
            "authority": "Banque du Liban (مصرف لبنان)",
            "fact": "1,507.5 from December 1997 to the end of January 2023 -- twenty-two years "
                    "-- then 15,000 from 2023-02-01 and 89,500 from 2023-11-01. EVERY STAGE OF "
                    "THE FAILURE IS DATED AND PUBLISHED, which is what makes this the desk's "
                    "reference case in peg failure and what makes `dk` its natural control"},
    "SYP": {"jurisdiction": "sy", "name": "Syrian pound (الليرة السورية)",
            "regime": "multiple_rates_partially_unpublished", "official": 13000.0,
            "parallel": "a black-market rate and a separate REMITTANCE rate; the published "
                        "official rate was moved repeatedly and the series is not continuous",
            "since": "2024-12-08",
            "authority": "Central Bank of Syria (مصرف سورية المركزي)",
            "fact": "THE PACK'S LIMIT CASE. The official rate has been reset by decree many "
                    "times, a separate remittance rate has existed for most of the sample, and "
                    "the 2024-12-08 political transition is a boundary at which the publishing "
                    "institutions themselves changed. Any SYP series that looks continuous "
                    "across it has been stitched by somebody, and the stitch is not published"},
}

FISCAL_YEAR_END = "12-31"          # Iraq, Jordan, Lebanon and Syria run the calendar year
#: IRAN IS THE EXCEPTION AND IT IS NOT A SMALL ONE: the Iranian fiscal year runs from 1 Farvardin
#: -- the day of Nowruz, which is DERIVED from the March equinox and is 20 or 21 March depending
#: on the year -- to 29 Esfand. So the Iranian budget, the subsidy envelope, the FX allocation
#: quotas and the state's own accounting year all break on a moving Gregorian day that no
#: quarter-end dummy can absorb. `iran_fiscal_year_start` derives it; `solar_hijri_year` names it.
FISCAL_YEAR_ENDS: dict[str, str] = {"iq": "12-31", "ir": "solar-hijri 29 Esfand (derived)",
                                    "jo": "12-31", "lb": "12-31", "sy": "12-31"}

NATIVE_LANGUAGES: tuple[str, ...] = ("ar", "fa", "ku", "en", "fr")
COT_CURRENCY = ""                  # no CFTC contract exists for IQD, IRR, JOD, LBP or SYP
EXPORT_ECONOMY = "split: two of the largest hydrocarbon reserve holders on earth (iq, ir) beside "\
                 "three import-dependent, remittance-financed economies (jo, lb, sy)"
RETAIL_LEVERAGE_REGIME = "mixed_and_largely_absent"
#: WHAT A LOCAL RETAIL TRADER CAN ACTUALLY DO, PER STATE. This is not trivia: it decides whether
#: a retail-ecology source exists to read at all, and four of the five answer differently.
RETAIL_LEVERAGE_BY_JURISDICTION: dict[str, str] = {
    "iq": "no domestic margin FX regime; the Iraq Stock Exchange is cash-only and the retail FX "
          "ground is the physical exchange-shop market in dollars and gold",
    "ir": "a LARGE domestic retail equity ecology on the Tehran Stock Exchange with millions of "
          "accounts, plus a deep retail gold-coin and hard-currency market; no access to any "
          "international broker, which is why the domestic ground is the only ground",
    "jo": "a small regulated market under the Jordan Securities Commission; retail FX margin is "
          "restricted and the Amman Stock Exchange is the retail venue",
    "lb": "the banking system's collapse destroyed the retail investment ecology; what is left "
          "is a cash dollar economy and a parallel-rate tracking culture that is itself a source",
    "sy": "NO RETAIL TRADING ECOLOGY: the Damascus Securities Exchange has no machine-readable "
          "tape, foreign-currency dealing has been criminalised at points in the sample, and the "
          "retail ground that exists is remittance pricing, not trading",
}

MISSION = ("mine the five states of the northern Gulf and the Levant as five machines: Iraq's "
           "dated SOMO OSP clock, its published OPEC+ compensation schedules and the "
           "court-ordered Kurdistan-Ceyhan shutdown; Iran's production as a function of dated US "
           "administrative acts, the two OPEC series that disagree about it, and the Bahar "
           "Azadi coin premium as a published inflation-expectation gauge; Jordan's 0.709 peg "
           "and Dead Sea potash into the fertiliser chain; Lebanon's fully dated peg failure "
           "against the Danish control; and Syria as the measured limit case whose absent layers "
           "are named with their mirror substitutes -- plus the shared Hormuz risk, the Arab Gas "
           "Pipeline, Levantine wheat dependence and the Gulf remittance corridor")

#: The instruments this pack may compile a cell against. Every one is in the broker registry and
#: none is a single-name equity. All five local currencies are absent (see TRANSMISSION_TARGETS).
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "XBRUSD", "XTIUSD",                     # the OSP clock, the quota, the pipeline, the strait
    "XNGUSD",                               # South Pars, the Arab Gas Pipeline, the winter deficit
    "XAUUSD", "XAGUSD",                     # the coin premium, the parallel-rate store of value
    "WHEAT", "CORN", "SOYBEAN",             # Levantine import dependence and the fertiliser chain
    "SUGAR", "COTTON",                      # the subsidy basket and the Euphrates cotton belt
    "USDTRY", "EURTRY", "GBPTRY",           # the transit state and the regional currency-crisis leg
    "USDILS", "EURILS",                     # the other executable regional-risk leg
    "EURUSD", "USDJPY", "USDCNH", "USDINR",  # the peg control, the Hormuz buyer, the mirror buyers
    "US500", "UK100", "GER40",              # the risk complex and the European gas/aid legs
)

#: EVERY LOCAL PRICE THIS PACK IS ABOUT, NAMED ABSENT WITH WHAT CARRIES IT. `proxies` must all
#: resolve in the broker registry -- a transmission target with an unquotable carrier is an
#: absence dressed as a route. Where a currency has TWO regimes, BOTH are named: a pack that
#: carries only the official rate of a country with a parallel market has recorded the number the
#: state publishes and lost the number the economy uses.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "IQD official (the Central Bank of Iraq administered rate, 1,320 since 2023-02-07)",
     "venue": "Central Bank of Iraq daily dollar auction and the compliance platform",
     "why": "the official rate is an ADMINISTERED number set by the Council of Ministers, so it "
            "moves on decree days and not on flow days; the executable legs are the crude the "
            "state sells for the dollars it auctions and the gold Iraqis buy when the premium "
            "widens",
     "regime": "administered; revalued 1,460 -> 1,320 on 2023-02-07",
     "proxies": ("XBRUSD", "XAUUSD", "USDTRY")},
    {"name": "IQD parallel (the Baghdad and Erbil market rate and its premium over official)",
     "venue": "the licensed exchange companies and the open market",
     "why": "THE PREMIUM IS THE INSTRUMENT. It widened sharply when US Treasury restrictions on "
            "dollar transfers through the CBI tightened through 2023 -- a dated administrative "
            "act with a published, measurable currency effect -- and it narrows when the "
            "platform clears transfers faster",
     "regime": "free market; premium over official is the observable",
     "proxies": ("XAUUSD", "USDTRY", "GBPTRY")},
    {"name": "IRR official (the 42,000 preferential rate decreed 2018-04-10)",
     "venue": "Bank Markazi administrative allocation for essential imports",
     "why": "a rationing price, not a market price; it prices the subsidy and the import quota "
            "and it has never been what an Iranian pays",
     "regime": "decreed; unchanged as a headline since 2018",
     "proxies": ("XBRUSD", "XAUUSD", "USDCNH")},
    {"name": "IRR free market and the NIMA/ETS exporter rates (the rial lattice)",
     "venue": "the Tehran open market and the integrated FX system for exporters",
     "why": "the free rate is what the household and the importer face and it is quoted daily in "
            "the Persian financial press; the NIMA rate sits between it and official, so Iran "
            "has a LATTICE of simultaneous prices and any claim must say which one it measured",
     "regime": "multiple simultaneous rates; an order of magnitude apart from official",
     "proxies": ("XAUUSD", "XAGUSD", "USDTRY")},
    {"name": "The Bahar Azadi gold coin (سکه بهار آزادی) and its premium over metal content",
     "venue": "the Tehran gold and coin market; quoted daily in the domestic press",
     "why": "A PUBLISHED DOMESTIC INFLATION-EXPECTATION GAUGE. The coin's price minus its own "
            "gold content is a pure expectations term, and Iranian household gold demand is a "
            "real component of regional physical demand -- which is why this is XAUUSD-relevant "
            "and not merely local colour",
     "regime": "a premium (حباب) over intrinsic metal value, quoted openly",
     "proxies": ("XAUUSD", "XAGUSD", "USDTRY")},
    {"name": "JOD (the Jordanian dinar, 0.7090 to the dollar since 1995-10-23)",
     "venue": "Central Bank of Jordan",
     "why": "THE CONTROL. A hard peg that has never broken, next door to one that broke "
            "completely; its information is in the CBJ's reserve line and its rate differential "
            "to the Fed, never in the spot rate, which does not move",
     "regime": "hard USD peg, unchanged for thirty years",
     "proxies": ("EURUSD", "XAUUSD", "USDILS")},
    {"name": "LBP official (1,507.5 -> 15,000 on 2023-02-01 -> 89,500 on 2023-11-01)",
     "venue": "Banque du Liban",
     "why": "the dated staircase of a peg's death; each step is a published administrative act "
            "with a day attached, which is what makes Lebanon a case study rather than an "
            "anecdote",
     "regime": "failed peg; three official levels in one sample",
     "proxies": ("XAUUSD", "USDTRY", "EURTRY")},
    {"name": "LBP parallel: the banknote rate, the Sayrafa platform rate and the 'lollar'",
     "venue": "the exchange-house market, the BdL Sayrafa platform (2021-2023) and the banks",
     "why": "THREE SIMULTANEOUS PRICES FOR ONE CURRENCY. A dollar deposit inside a Lebanese bank "
            "('lollar') was worth a fraction of a banknote dollar at the same moment, and "
            "Sayrafa was a fourth number in between. Any Lebanese series must name which",
     "regime": "multiple parallel rates; the spread between them is the instrument",
     "proxies": ("XAUUSD", "EURILS", "USDTRY")},
    {"name": "SYP official and the separate remittance rate",
     "venue": "Central Bank of Syria and the licensed transfer companies",
     "why": "the official rate has been reset by decree repeatedly and a distinct remittance rate "
            "has run beside it for most of the sample; the 2024-12-08 transition breaks the "
            "series again",
     "regime": "multiple rates, partially unpublished, discontinuous across 2024-12-08",
     "proxies": ("WHEAT", "XAUUSD", "USDTRY")},
    {"name": "Basrah Medium and Basrah Heavy OSP differentials to the Oman/Dubai average",
     "venue": "SOMO monthly announcement",
     "why": "the two grades Iraq actually sells east of Suez; the OSP is an ADMINISTERED, DATED "
            "differential and therefore testable in a way a spot price is not, and no CFD quotes "
            "either grade",
     "regime": "monthly administered differential to a named benchmark",
     "proxies": ("XBRUSD", "XTIUSD", "USDINR")},
    {"name": "Iranian Light and Iranian Heavy export prices and their discounts to Brent",
     "venue": "bilateral; the discount is reported, never published by the seller",
     "why": "the sanctions discount is the price of the political act; it is visible only in "
            "buyer-side reporting and in mirror customs values, so it is a REPORTED observable "
            "and never a series this desk can carry",
     "regime": "bilateral, discounted, unpublished by the seller",
     "proxies": ("XBRUSD", "XTIUSD", "USDCNH")},
    {"name": "Potash (MOP) and phosphate rock contract prices",
     "venue": "the international fertiliser contract market; Arab Potash and JPMC are the "
              "Jordanian producers",
     "why": "NOT A BROKER SYMBOL AND NOT AN EQUITY. Potash and phosphate are INPUT COSTS to the "
            "grain complex, so the lawful route is the fertiliser-cost chain into CORN and "
            "WHEAT, with the control naming the two other determinants -- natural gas (ammonia) "
            "and the Belarus/Russia supply share -- so a Jordanian claim is not a gas claim",
     "regime": "annual and semi-annual contract settlements, quoted publicly in trade press",
     "proxies": ("CORN", "WHEAT", "SOYBEAN")},
    {"name": "ISX (Iraq), TSE and IFB (Iran), ASE (Jordan), BSE (Lebanon), DSE (Syria) indices",
     "venue": "the five national exchanges",
     "why": "no CFD is quoted on any of them and three of the five publish no machine-readable "
            "tape; the local index is an OBSERVABLE and the executable leg is the risk complex",
     "regime": "n/a (equity indices)",
     "proxies": ("US500", "UK100", "GER40")},
    {"name": "Lebanese eurobonds (in default since 2020-03-07) and Jordanian USD sovereigns",
     "venue": "the international bond market",
     "why": "the Lebanese curve is the price of a completed default and the Jordanian curve is "
            "the price of an IMF programme that held; neither is quoted here, so the credit leg "
            "is declared UNMEASURED by name rather than proxied silently",
     "regime": "n/a (credit)",
     "proxies": ("US500", "EURUSD", "USDTRY")},
    {"name": "The Iraqi, Jordanian and Lebanese interbank and policy rates",
     "venue": "CBI, CBJ and BdL published rates",
     "why": "Jordan imports the Fed's cycle mechanically, so the CBJ-minus-Fed spread is the only "
            "local information in a Jordanian rate; Iraq's and Lebanon's policy rates are "
            "administered and are fiscal instruments rather than monetary ones",
     "regime": "n/a (rates, not parities)",
     "proxies": ("US500", "EURUSD", "XAUUSD")},
)

# --------------------------------------------------------------------------- the central banks
#: The pack-level central bank is the CBI, because IQD is the pack's declared currency. The other
#: four are carried in CENTRAL_BANKS: a pack that describes one monetary authority and calls it
#: "the region" has erased the fact that one of these five defends a peg, one administers a
#: lattice of rates, one ran out of the ability to defend anything, and one publishes little.
CENTRAL_BANK: dict[str, Any] = {
    "name": "Central Bank of Iraq -- البنك المركزي العراقي",
    "short": "CBI",
    "framework": "administered exchange rate with a daily dollar auction",
    "committee": "the Governor and the Board; the exchange rate itself is set by the Council of "
                 "Ministers, not by the bank, which is why an Iraqi 'currency decision' is a "
                 "CABINET event and not a central-bank one",
    "policy_instrument": "the daily dollar auction/platform allocation, the administered official "
                         "rate, and reserve and transfer-compliance rules",
    "mandate": "price and exchange-rate stability; in practice the CBI is the channel through "
               "which oil dollars are converted into dinars for the salary bill, so its "
               "operations are FISCAL plumbing with a monetary label",
    "decision_rule": "the official rate changes by government decision on announced days (the "
                     "2023-02-07 revaluation from 1,460 to 1,320 is the dated case); the "
                     "auction/platform allocation is daily",
    "decision_calendar_rule": "no scheduled policy calendar. The real clock is (a) the daily "
                              "auction result, (b) the monthly oil-revenue transfer, and (c) "
                              "US Treasury compliance actions, which are published in Washington "
                              "and not in Baghdad",
    "decision_dates": (),
    "dates_status": "DECLARED EMPTY ON PURPOSE. There is no scheduled Iraqi rate calendar; "
                    "inventing one would manufacture events. The dated events are the CABINET "
                    "revaluations and the US Treasury actions, both of which are published",
    "decision_time_utc": "08:00",
    "announce_local": "Baghdad is UTC+3 all year with NO daylight saving since 2008, which makes "
                      "an Iraqi session study stable where a European one is not",
    "dst_rule": "none for Iraq (UTC+3); IRAN ABOLISHED DST IN 2022 and is UTC+3:30 all year; "
                "Jordan moved to permanent UTC+3 from 2022-10-28; Lebanon and Syria still "
                "observe European-style DST -- FOUR DIFFERENT CLOCK RULES among five neighbours",
    "minutes_lag_days": 0,
    "publication_classes": ("daily_auction_result", "monthly_statistical_bulletin",
                            "annual_report", "foreign_reserves", "platform_notice",
                            "exchange_rate_decree"),
    "policy_rate_series": "CBI:policy_rate",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "the parallel-market rate: it is the market's own forecast of the "
                       "administered rate's sustainability, published daily by the exchange "
                       "companies",
    "consensus_proxy_trap": "the parallel rate also carries a COMPLIANCE-FRICTION term -- how "
                            "hard it is to get a dollar transfer approved this week -- so a "
                            "widening premium is a plumbing fact before it is a devaluation "
                            "expectation, and separating the two is the work",
    "reserves_clock": "monthly foreign-reserve line in the CBI statistical bulletin, plus the "
                      "IMF's published Iraq data in the Article IV cycle",
    "programme": "no standing IMF programme for Iraq; Jordan has an Extended Fund Facility and "
                 "Lebanon has a staff-level agreement that was never implemented",
    "off_cycle": ("2023-02-07 the Council of Ministers revalued the dinar to 1,320",
                  "2023-2024 the phased ban on cash dollar transactions and the move of all "
                  "transfers onto the screened platform"),
    "root": "https://cbi.iq",
}

#: THE OTHER FOUR MONETARY AUTHORITIES. Each is a DIFFERENT KIND of institution and the pack is
#: built on that difference: a defender, an administrator, a failed defender and a near-silent one.
CENTRAL_BANKS: dict[str, dict[str, Any]] = {
    "iq": {"name": "Central Bank of Iraq -- البنك المركزي العراقي", "framework": "administered",
           "root": "https://cbi.iq",
           "rule": "sells the state's oil dollars through a daily auction; the RATE is a cabinet "
                   "decision and the PREMIUM is the market's verdict on it"},
    "ir": {"name": "Central Bank of Iran / Bank Markazi -- بانک مرکزی جمهوری اسلامی ایران",
           "framework": "multiple_rates", "root": "https://www.cbi.ir",
           "rule": "administers a LATTICE: a 42,000 preferential rate for essential imports, the "
                   "NIMA/ETS integrated-market rates for exporters, and a free market it does "
                   "not set. Every one of the three is a real price for somebody, and none of "
                   "them is 'the' rial"},
    "jo": {"name": "Central Bank of Jordan -- البنك المركزي الأردني", "framework": "hard_peg",
           "root": "https://www.cbj.gov.jo",
           "rule": "THE CONTROL. Defends 0.7090 and follows the Fed, usually by less than the "
                   "full step; the CBJ-minus-Fed spread and the reserve line are the only local "
                   "information, and both are published monthly"},
    "lb": {"name": "Banque du Liban -- مصرف لبنان", "framework": "failed_peg",
           "root": "https://www.bdl.gov.lb",
           "rule": "defended 1,507.5 for twenty-two years with financial engineering, then could "
                   "not; ran Sayrafa as a platform rate from 2021 to 2023 and moved the official "
                   "rate to 15,000 and then 89,500. Its published balance sheet is the single "
                   "most-read document in Lebanese economics"},
    "sy": {"name": "Central Bank of Syria -- مصرف سورية المركزي", "framework": "administered",
           "root": "https://cb.gov.sy",
           "rule": "publishes an official rate and, separately, a remittance rate; the series is "
                   "not continuous and the 2024-12-08 transition changed the institution itself. "
                   "Its credibility is labelled UNRELIABLE in SOURCE_CLASSES on purpose -- that "
                   "is a measurement, not an insult"},
}
# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Central Bank of Iraq daily dollar auction / platform allocation result",
     "local": "published each business day, Sunday to Thursday, Asia/Baghdad (UTC+3)",
     "time_utc": "08:00", "time_utc_dst": "08:00",
     "dst_rule": "none; Iraq has kept UTC+3 with no daylight saving since 2008",
     "instruments": ("XBRUSD", "XAUUSD", "USDTRY"), "window_minutes": 60,
     "why": "the auction is where the state's oil dollars become dinars for the salary bill; the "
            "ALLOCATED VOLUME and the share rejected on compliance grounds are the two numbers "
            "that move the parallel premium, and both are published the same day"},
    {"name": "Iraqi parallel-market rate (Baghdad Kifah street and the Erbil market)",
     "local": "quoted continuously by the exchange companies; the daily reference is a morning "
              "print reported by the financial press",
     "time_utc": "07:00", "time_utc_dst": "07:00", "dst_rule": "none; UTC+3 all year",
     "instruments": ("XAUUSD", "USDTRY", "GBPTRY"), "window_minutes": 90,
     "why": "the PREMIUM over the official 1,320 is the observable this pack cares about; it is "
            "a compliance-friction gauge first and a devaluation-expectation gauge second"},
    {"name": "Bank Markazi official and NIMA/ETS integrated-market rates",
     "local": "published on the bank's own portal; the free-market rate is quoted by the Tehran "
              "market and reported by the domestic press, Asia/Tehran (UTC+3:30)",
     "time_utc": "06:30", "time_utc_dst": "06:30",
     "dst_rule": "none since 2022: IRAN ABOLISHED DAYLIGHT SAVING, so Tehran is UTC+3:30 all "
                 "year and the half-hour offset is permanent",
     "instruments": ("XAUUSD", "XAGUSD", "USDTRY"), "window_minutes": 120,
     "why": "THREE PRICES AT ONE MOMENT. The spread between the free rate and the NIMA rate is "
            "the exporter's implicit tax and the spread to 42,000 is the importer's subsidy"},
    {"name": "Tehran gold-coin (Bahar Azadi) session and the published premium",
     "local": "the Tehran coin market's morning and afternoon prints",
     "time_utc": "06:30", "time_utc_dst": "06:30", "dst_rule": "none; UTC+3:30 all year",
     "instruments": ("XAUUSD", "XAGUSD"), "window_minutes": 120,
     "why": "the coin price minus its own metal content is a PURE EXPECTATIONS TERM, quoted "
            "publicly every day; it is the only published inflation-expectation gauge in the "
            "pack and it is denominated in the metal this desk can trade"},
    {"name": "Central Bank of Jordan rate decisions, announced within hours of the FOMC",
     "local": "Amman, permanent UTC+3 since 2022-10-28",
     "time_utc": "19:30", "time_utc_dst": "19:30",
     "dst_rule": "none since 2022-10-28, when Jordan moved to permanent UTC+3 and stopped "
                 "changing clocks -- a dated convention change that shifts every Jordanian "
                 "intraday window by an hour on one side of it",
     "instruments": ("EURUSD", "XAUUSD", "USDILS"), "window_minutes": 60,
     "why": "the CBJ has repeatedly moved by LESS than the Fed's step while holding the peg; the "
            "gap is the only degree of freedom a hard peg has and it is published"},
    {"name": "Banque du Liban official rate and the Sayrafa platform print (2021-2023)",
     "local": "Beirut, UTC+2 winter / UTC+3 summer -- Lebanon STILL CHANGES CLOCKS",
     "time_utc": "08:00", "time_utc_dst": "07:00",
     "dst_rule": "European-style DST, last Sunday of March to last Sunday of October; in 2023 "
                 "the change was postponed by decision and then reversed within days, so the "
                 "country ran on TWO CLOCKS at once for a week -- a real timestamp hazard",
     "instruments": ("XAUUSD", "USDTRY", "EURTRY"), "window_minutes": 120,
     "why": "Sayrafa was a platform rate between the official and the banknote rate; when it "
            "operated, three prices existed simultaneously and a series that does not say which "
            "one it sampled is not a series"},
    {"name": "SOMO monthly Official Selling Price announcement (Basrah Medium and Heavy)",
     "local": "announced for the following month's liftings, after Saudi Aramco's OSP sets the "
              "reference",
     "time_utc": "10:00", "time_utc_dst": "10:00", "dst_rule": "none",
     "instruments": ("XBRUSD", "XTIUSD", "USDINR"), "window_minutes": 180,
     "why": "AN ADMINISTERED, DATED DIFFERENTIAL. SOMO sets Basrah Medium and Basrah Heavy to the "
            "Oman/Dubai average for Asia and to other markers for Europe and the US; the "
            "announcement is the event and the differential is the number"},
    {"name": "Central Bank of Syria official rate and the separate remittance rate",
     "local": "Damascus; Syria observes European-style DST",
     "time_utc": "08:00", "time_utc_dst": "07:00",
     "dst_rule": "European-style DST; the 2022 and 2023 changes were announced by decree with "
                 "little notice",
     "instruments": ("WHEAT", "XAUUSD", "USDTRY"), "window_minutes": 180,
     "why": "REGISTERED WITH ITS CREDIBILITY LABELLED. The official print exists; it is not the "
            "price at which a Syrian household converts a remittance, and the two are published "
            "separately when they are published at all"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "SOMO monthly OSP announcement for the following month's liftings",
     "kind": "day_of_month", "days": (5, 6, 7), "roll": "next", "window_utc": ("08:00", "14:00"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "why": "the Basrah differentials are set in the first week for next month's cargoes, after "
            "the Saudi reference lands; the ORDER of the two announcements is the identification"},
    {"name": "Iraqi monthly oil export volume and revenue publication",
     "kind": "month_end", "roll": "next", "window_utc": ("08:00", "13:00"),
     "instruments": ("XBRUSD", "XTIUSD", "US500"),
     "why": "the Oil Ministry publishes BOTH the volume and the realised revenue within days of "
            "month end, which means the realised average price is computable -- a transparency "
            "almost no other OPEC member offers"},
    {"name": "The Iraqi salary bill: the monthly conversion of oil dollars into dinars",
     "kind": "month_end", "roll": "previous", "window_utc": ("07:00", "12:00"),
     "instruments": ("XAUUSD", "USDTRY", "GBPTRY"),
     "why": "the state pays several million public salaries a month and the dinars come from the "
            "CBI auction; the month-end conversion is a real, dated dollar demand event and the "
            "parallel premium moves around it"},
    {"name": "The Iranian fiscal year: 1 Farvardin to 29 Esfand (DERIVED from the equinox)",
     "kind": "fiscal_year_end", "roll": "previous", "window_utc": ("06:00", "12:00"),
     "instruments": ("XBRUSD", "XAUUSD", "XNGUSD"),
     "why": "the budget, the FX allocation quotas and the subsidy envelope all break on Nowruz, "
            "which is 20 or 21 March depending on the equinox; no Gregorian quarter dummy "
            "absorbs it and `iran_fiscal_year_start` derives it rather than typing it"},
    {"name": "The Nowruz shutdown: roughly two weeks of closed Iranian markets",
     "kind": "fixed_window", "roll": "next", "window_utc": ("00:00", "23:59"),
     "instruments": ("XBRUSD", "XAUUSD", "XNGUSD"),
     "why": "Iran closes for 1-4 Farvardin and again for 12-13 Farvardin, and the practical "
            "shutdown runs about thirteen days to Sizdah Bedar; Iranian physical gold and FX "
            "demand stops and restarts on a DERIVABLE day"},
    {"name": "OPEC+ ministerial, JMMC and the Iraqi compensation-schedule filing",
     "kind": "day_of_month", "days": (1, 2, 3, 4), "roll": "next",
     "window_utc": ("10:00", "16:00"), "instruments": ("XBRUSD", "XTIUSD"),
     "why": "Iraq's compensation schedules are submitted to and published by the Secretariat "
            "around the ministerial cycle; they are DATED PROMISES TO UNDER-PRODUCE by named "
            "volumes in named months, which is a testable commitment and not a forecast"},
    {"name": "Jordanian and Lebanese month-end remittance settlement",
     "kind": "month_end", "roll": "previous", "window_utc": ("07:00", "14:00"),
     "instruments": ("XAUUSD", "EURUSD", "UK100"),
     "why": "the Gulf and European diasporas remit on the monthly salary cycle; in Lebanon the "
            "remittance is frequently converted straight into banknote dollars or gold, which is "
            "why this is a metal flow and not only an FX one"},
    {"name": "The Levantine wheat tender cycle (public tenders and UN-financed purchases)",
     "kind": "irregular", "roll": "next", "window_utc": ("08:00", "15:00"),
     "instruments": ("WHEAT", "CORN", "SUGAR"),
     "why": "Lebanon and Syria buy wheat in dated public and agency-financed tenders; a tender "
            "is an announced quantity on an announced day, which is the cleanest demand event a "
            "grain study can ask for"},
    {"name": "Arab Potash and JPMC contract settlements and shipment cycles",
     "kind": "quarter_end", "roll": "previous", "window_utc": ("08:00", "14:00"),
     "instruments": ("CORN", "WHEAT", "SOYBEAN"),
     "why": "potash and phosphate contracts settle on announced terms and ship from Aqaba; the "
            "cost feeds planting-season economics, so the grain leg is the executable end of a "
            "Jordanian mining fact"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Iraq Stock Exchange (ISX) -- سوق العراق للأوراق المالية",
     "index_symbols": (),
     "open_local": "10:00", "close_local": "12:30", "open_utc": "07:00", "close_utc": "09:30",
     "dst_rule": "none; Asia/Baghdad is UTC+3 all year",
     "auction": "pre-open then continuous; settlement T+2, cash market only",
     "expiry_rule": "no listed derivatives and no public intraday tape; there is no expiry clock "
                    "to mine and the pack says so rather than inventing one",
     "holidays": "the Iraqi national calendar plus the sighted feasts, and Iraq observes BOTH "
                 "the Sunni and the Shia feast calendars, which sometimes differ by a day",
     "notes": "NO CFD IS QUOTED on the ISX index; it enters as a transmission target. The "
              "exchange is dominated by banks and telecoms and is a two-lane EVENT venue only"},
    {"name": "Tehran Stock Exchange (TSE) and Iran Fara Bourse -- بورس اوراق بهادار تهران",
     "index_symbols": (),
     "open_local": "09:00", "close_local": "12:30", "open_utc": "05:30", "close_utc": "09:00",
     "dst_rule": "none since 2022; Asia/Tehran is UTC+3:30 all year",
     "auction": "pre-open 08:45, continuous to 12:30, with statutory price limits that bind "
                "frequently and produce queue dynamics rather than prices",
     "expiry_rule": "a domestic options and futures market exists on the IFB; no international "
                    "access and no CFD, so it is an OBSERVABLE and never an instrument here",
     "holidays": "the Solar Hijri national calendar (Nowruz and the Farvardin holidays derived "
                 "from the equinox) plus the Shia feast calendar -- the most distinctive "
                 "market calendar in this pack by a wide margin",
     "notes": "A LARGE RETAIL MARKET WITH MILLIONS OF ACCOUNTS, which is why Iran has a genuine "
              "retail-ecology layer that Syria does not. The index is quoted in rials, so a "
              "nominal index rise during a devaluation is a currency fact, not an equity one"},
    {"name": "Amman Stock Exchange (ASE) -- بورصة عمان",
     "index_symbols": (),
     "open_local": "10:00", "close_local": "13:00", "open_utc": "07:00", "close_utc": "10:00",
     "dst_rule": "none since 2022-10-28; Jordan is permanently UTC+3",
     "auction": "opening auction then continuous; the ASE publishes daily foreign-investor "
                "buy/sell statistics, which is the pack's cleanest local flow series",
     "expiry_rule": "no listed index derivatives with a public tape",
     "holidays": "the Jordanian national calendar (25 May Independence Day) and the sighted "
                 "feasts announced by the Iftaa' Department",
     "notes": "the most orderly venue of the five and the only one whose currency does not move; "
              "its FOREIGN OWNERSHIP share is a regional-risk gauge because the marginal holder "
              "is Gulf money"},
    {"name": "Beirut Stock Exchange (BSE) -- بورصة بيروت",
     "index_symbols": (),
     "open_local": "09:30", "close_local": "12:30", "open_utc": "07:30", "close_utc": "10:30",
     "dst_rule": "European-style DST; Lebanon is UTC+2 winter and UTC+3 summer",
     "auction": "a thin continuous session; trading has at times been dominated by Solidere and "
                "by bank shares used as a devaluation hedge",
     "expiry_rule": "none listed with a public tape",
     "holidays": "the Lebanese calendar, which is the richest in this pack: BOTH Western and "
                 "Orthodox Easter, the Annunciation on 25 March as a shared Christian-Muslim "
                 "holiday, and the Islamic feasts announced by two separate authorities",
     "notes": "the exchange became a DEVALUATION HEDGE rather than an equity market after 2019: "
              "prices are in pounds, so the index rose while the economy collapsed. That is the "
              "single most instructive chart in the pack and it is not an equity signal"},
    {"name": "Damascus Securities Exchange (DSE) -- سوق دمشق للأوراق المالية",
     "index_symbols": (),
     "open_local": "10:30", "close_local": "12:30", "open_utc": "07:30", "close_utc": "09:30",
     "dst_rule": "European-style DST",
     "auction": "a very thin session; NO MACHINE-READABLE TAPE IS PUBLISHED",
     "expiry_rule": "none",
     "holidays": "the Syrian national calendar, which CHANGED at the 2024-12-08 transition -- "
                 "holidays were abolished and added, which is itself the observable",
     "notes": "DECLARED THIN ON PURPOSE. The DSE is named so that its absence of a tape is a "
              "recorded measurement rather than a gap; every Syrian mechanism in this pack "
              "terminates in wheat, cotton, gold or the lira legs"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "tehran_morning", "start_utc": "05:30", "end_utc": "09:00",
     "notes": "the earliest cash session in the pack; Tehran's UTC+3:30 offset means the Iranian "
              "gold-coin and FX prints land before any Arab market opens"},
    {"name": "levant_baghdad_morning", "start_utc": "07:00", "end_utc": "10:30",
     "notes": "the union of the Iraqi, Jordanian and Lebanese cash sessions; it closes before "
              "London's first hour is over, so a regional reaction is observable in isolation"},
    {"name": "somo_osp_window", "start_utc": "09:00", "end_utc": "14:00",
     "notes": "the first-week-of-month SOMO announcement window, after the Saudi OSP reference"},
    {"name": "us_treasury_action_window", "start_utc": "14:00", "end_utc": "21:00",
     "notes": "THE MOST IMPORTANT WINDOW IN THIS PACK AND IT IS IN WASHINGTON. OFAC designations, "
              "general licences and Federal Register notices land in US hours and are the dated "
              "acts that move Iranian and Iraqi dollar plumbing"},
    {"name": "cbj_fomc_echo", "start_utc": "19:00", "end_utc": "21:00",
     "notes": "the evening in which the Central Bank of Jordan publishes whether it matched the "
              "Fed's step or moved by less -- the peg's only degree of freedom"},
    {"name": "nowruz_shutdown", "start_utc": "00:00", "end_utc": "23:59",
     "notes": "the derived two-week Iranian closure from 1 Farvardin to 13 Farvardin; a window "
              "in which Iranian physical demand simply is not there"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "SOMO monthly Official Selling Prices (Basrah Medium, Basrah Heavy)",
     "cadence": "monthly", "time_utc": "10:00", "source": "SOMO / Iraqi Ministry of Oil",
     "actual_series": "SOMO:osp_basrah_differential", "expected_series": "UNMEASURED",
     "notes": "the first week of the month, after the Saudi reference; the two grades are "
              "announced together and the Asia differential is the number that travels"},
    {"name": "Iraqi Ministry of Oil monthly export volumes and revenues",
     "cadence": "monthly", "time_utc": "08:00", "source": "Iraqi Ministry of Oil",
     "actual_series": "MOO:monthly_exports_bbl", "expected_series": "UNMEASURED",
     "notes": "volume AND revenue, within days of month end, so the realised average price is "
              "computable; Kurdish exports are reported separately when they flow at all"},
    {"name": "OPEC Monthly Oil Market Report: Iraq and Iran, BOTH production tables",
     "cadence": "monthly", "time_utc": "11:00", "source": "OPEC Secretariat",
     "actual_series": "OPEC:iran_secondary_sources", "expected_series": "OPEC:iran_direct_comm",
     "notes": "THE TWO SERIES DISAGREE AND THE GAP IS THE OBSERVABLE. Direct communication is "
              "what the member states, and secondary sources are what the trackers say; for "
              "Iran the difference has run to hundreds of thousands of barrels a day"},
    {"name": "Central Bank of Iraq daily auction/platform result",
     "cadence": "daily", "time_utc": "08:00", "source": "CBI",
     "actual_series": "CBI:auction_allocation", "expected_series": "UNMEASURED",
     "notes": "the allocated volume and the compliance rejection share; the parallel premium is "
              "the market's same-day verdict on both"},
    {"name": "US OFAC designations, general licences and Federal Register notices",
     "cadence": "irregular", "time_utc": "17:00", "source": "US Treasury / Federal Register",
     "actual_series": "OFAC:designation_events", "expected_series": "n/a",
     "notes": "THE DATED ADMINISTRATIVE ACTS THAT SET IRANIAN OUTPUT AND IRAQI DOLLAR PLUMBING. "
              "Published in Washington, machine-readable, and the cleanest event clock in the "
              "pack precisely because it is not published by any of the five states"},
    {"name": "Bank Markazi rate tables and the reported Tehran free-market rate",
     "cadence": "daily", "time_utc": "06:30", "source": "Bank Markazi / domestic press",
     "actual_series": "CBI_IR:free_market_rate", "expected_series": "CBI_IR:official_rate",
     "notes": "the official, NIMA and free rates are three different prints; the domestic press "
              "carries the free rate and the coin premium beside it"},
    {"name": "Central Bank of Jordan policy decision and monthly reserves",
     "cadence": "monthly", "time_utc": "19:30", "source": "CBJ",
     "actual_series": "CBJ:policy_rate", "expected_series": "FOMC:target_range",
     "notes": "the CBJ has repeatedly moved by less than the Fed while holding 0.7090; the gap "
              "and the reserve line together are the peg's health check"},
    {"name": "Banque du Liban weekly balance sheet and the published official rate",
     "cadence": "weekly", "time_utc": "12:00", "source": "BdL",
     "actual_series": "BDL:fx_reserves", "expected_series": "UNMEASURED",
     "notes": "the most-read document in Lebanese economics; the reserve line is what the "
              "parallel rate trades against and the official rate is what the state books at"},
    {"name": "Jordanian Department of Statistics CPI, trade and tourism",
     "cadence": "monthly", "time_utc": "08:00", "source": "DoS Jordan",
     "actual_series": "DOS:cpi_trade", "expected_series": "UNMEASURED",
     "notes": "Jordan is the only one of the five publishing a complete, uninterrupted, "
              "internationally reconciled statistical series across the whole sample"},
    {"name": "UN Comtrade and the Chinese, Indian and Turkish customs portals (MIRROR data)",
     "cadence": "monthly", "time_utc": "02:00",
     "source": "UN Comtrade; China GACC; India DGCI&S; Turkey TUIK",
     "actual_series": "MIRROR:partner_reported_trade", "expected_series": "n/a",
     "notes": "THE SUBSTITUTE FOR EVERY ABSENT SYRIAN AND IRANIAN TRADE SERIES. What a country "
              "does not publish, its partners do; the mirror is lagged and incomplete and it is "
              "the lawful ground that exists"},
    {"name": "FAO/GIEWS and WFP market monitoring for Syria, Lebanon and Jordan",
     "cadence": "monthly", "time_utc": "10:00", "source": "FAO / WFP",
     "actual_series": "WFP:food_basket_price", "expected_series": "n/a",
     "notes": "crop assessments, import requirements and a priced food basket by governorate; "
              "the only systematic price series that still exists for parts of Syria"},
    {"name": "IMF Article IV reports and the published statistical appendices",
     "cadence": "annual", "time_utc": "14:00", "source": "International Monetary Fund",
     "actual_series": "IMF:article_iv_tables", "expected_series": "n/a",
     "notes": "Jordan's is current and detailed; Iraq's and Lebanon's exist; Iran's is "
              "intermittent and Syria's has not been done since before the war -- which is "
              "itself the measurement, and it is named in NO_LAWFUL_GROUND"},
)
# --------------------------------------------------------------------------- holidays and clocks
#: FIVE NEIGHBOURS, FOUR DECLARED WEEKEND REGIMES, THREE DISTINCT PAIRS AND ONLY THREE DAYS A
#: WEEK ON WHICH ALL FIVE ARE OPEN. Python weekday(): Mon=0 .. Thu=3, Fri=4, Sat=5, Sun=6.
#: Iraq, Jordan and Syria rest Friday-Saturday; LEBANON RESTS SATURDAY-SUNDAY like a European
#: market; IRAN RESTS THURSDAY-FRIDAY. Lebanon's weekend and Iran's are DISJOINT, so a "regional
#: session" is a fiction: the only days every one of the five is open are Monday, Tuesday and
#: Wednesday, and `common_session_weekdays()` derives that rather than asserting it.
WEEKENDS: dict[str, tuple[int, ...]] = {
    "iq": (4, 5), "ir": (3, 4), "jo": (4, 5), "lb": (5, 6), "sy": (4, 5),
}
#: The pack-level default for the framework's HolidayRule row: the Friday-Saturday weekend three
#: of the five keep. The other two are in `WEEKENDS` and in the rule text, never lost.
WEEKEND_WEEKDAYS: tuple[int, int] = (4, 5)

#: FIXED SOLAR NATIONAL DAYS, DERIVED AND NEVER TYPED INTO A YEAR TABLE. Iran has none in this
#: table on purpose: every Iranian national day sits on the SOLAR HIJRI calendar and is derived
#: from Nowruz by `iran_national`, which is the distinguishing calendar fact of this pack.
FIXED_NATIONAL: dict[str, tuple[tuple[int, int, str], ...]] = {
    "iq": ((1, 1, "رأس السنة الميلادية"), (1, 6, "عيد الجيش العراقي"),
           (3, 21, "نوروز / نەورۆز (عيد وطني في العراق وإقليم كردستان)"),
           (5, 1, "عيد العمال"), (7, 14, "عيد الجمهورية"), (10, 3, "عيد الاستقلال"),
           (12, 10, "يوم النصر على داعش")),
    "jo": ((1, 1, "رأس السنة الميلادية"), (5, 1, "عيد العمال"),
           (5, 25, "عيد الاستقلال الأردني"), (12, 25, "عيد الميلاد المجيد")),
    "lb": ((1, 1, "رأس السنة الميلادية"), (1, 6, "عيد الميلاد عند الطوائف الأرمنية"),
           (2, 9, "عيد مار مارون"), (3, 25, "عيد البشارة (عيد مشترك مسيحي إسلامي)"),
           (5, 1, "عيد العمال"), (5, 6, "عيد شهداء لبنان"),
           (8, 15, "عيد انتقال السيدة العذراء"), (11, 1, "عيد جميع القديسين"),
           (11, 22, "عيد الاستقلال اللبناني"), (12, 25, "عيد الميلاد المجيد")),
    "sy": ((1, 1, "رأس السنة الميلادية"), (3, 21, "عيد الأم"), (4, 17, "عيد الجلاء"),
           (5, 1, "عيد العمال"), (5, 6, "عيد الشهداء"), (12, 25, "عيد الميلاد المجيد")),
}
#: SYRIA'S CALENDAR CHANGED ON A DATE, AND THE CHANGE IS THE OBSERVABLE. The 8 March Revolution
#: Day and the 6 October War Day were the previous order's holidays and were dropped after the
#: 2024-12-08 transition; 8 December was added as the anniversary of the fall. A study that uses
#: one Syrian holiday calendar across the whole sample is using a calendar that no longer exists.
SYRIA_CALENDAR_BREAK = date(2024, 12, 8)
SYRIA_PRE_TRANSITION: tuple[tuple[int, int, str], ...] = (
    (3, 8, "عيد الثورة (ملغى بعد 2024-12-08)"),
    (10, 6, "ذكرى حرب تشرين التحريرية (ملغى بعد 2024-12-08)"),
)
SYRIA_POST_TRANSITION: tuple[tuple[int, int, str], ...] = (
    (12, 8, "ذكرى سقوط النظام (أضيف اعتبارا من 2025)"),
)

#: WHO ANNOUNCES THE FEAST, PER STATE. This is not decoration: IRAQ AND LEBANON EACH HAVE TWO
#: AUTHORITIES and the Sunni and Shia announcements differ by a day often enough to mislabel an
#: event sample, and IRAN'S announcement is routinely a day after Saudi Arabia's.
SIGHTING_AUTHORITIES: dict[str, str] = {
    "iq": "ديوان الوقف السني وديوان الوقف الشيعي في بغداد، ومكتب المرجعية الدينية العليا في النجف",
    "ir": "دفتر مقام معظم رهبری (ستاد استهلال) — اعلام رسمی معمولا یک روز پس از عربستان",
    "jo": "دائرة الإفتاء العام في المملكة الأردنية الهاشمية",
    "lb": "دار الفتوى للطائفة السنية والمجلس الإسلامي الشيعي الأعلى",
    "sy": "وزارة الأوقاف السورية",
}


def sighting_status(kind: str) -> str:
    """One status line naming EVERY state's own sighting authority.

    A lunar row whose status says only "announced" has lost the fact that five authorities
    announce, two states carry two authorities each, and Iran's is usually a day later.
    """
    parts = [f"{cc}={SIGHTING_AUTHORITIES[cc]}" for cc in JURISDICTIONS]
    return f"{kind} :: " + " | ".join(parts)


#: THE ISLAMIC-CALENDAR FEASTS, TYPED. They cannot be computed: each is fixed by a SIGHTING
#: announced the evening before by the authorities above, and the five states do not agree.
#: Row: (date, name, the states that observe it on that date, status).
LUNAR_HOLIDAYS: dict[int, tuple[tuple[date, str, tuple[str, ...], str], ...]] = {
    2024: (
        (date(2024, 2, 8), "المبعث النبوي / الإسراء والمعراج", ("iq", "ir", "jo", "lb", "sy"),
         sighting_status("ANNOUNCED")),
        (date(2024, 4, 10), "عيد الفطر (اليوم الأول)", ("iq", "ir", "jo", "lb", "sy"),
         sighting_status("ANNOUNCED")),
        (date(2024, 4, 11), "عيد الفطر (اليوم الثاني)", ("iq", "ir", "jo", "lb", "sy"),
         sighting_status("ANNOUNCED")),
        (date(2024, 6, 15), "يوم عرفة", ("iq", "jo"), sighting_status("ANNOUNCED")),
        (date(2024, 6, 16), "عيد الأضحى (اليوم الأول)", ("iq", "ir", "jo", "lb", "sy"),
         sighting_status("ANNOUNCED")),
        (date(2024, 6, 17), "عيد الأضحى (اليوم الثاني)", ("iq", "ir", "jo", "lb", "sy"),
         sighting_status("ANNOUNCED")),
        (date(2024, 6, 24), "عيد الغدير", ("iq", "ir"), sighting_status("ANNOUNCED")),
        (date(2024, 7, 7), "رأس السنة الهجرية", ("iq", "ir", "jo", "lb", "sy"),
         sighting_status("ANNOUNCED")),
        (date(2024, 7, 16), "عاشوراء", ("iq", "ir", "lb", "sy"), sighting_status("ANNOUNCED")),
        (date(2024, 8, 25), "الأربعين", ("iq", "ir"), sighting_status("ANNOUNCED")),
        (date(2024, 9, 15), "المولد النبوي (التاريخ السني، 12 ربيع الأول)",
         ("iq", "jo", "lb", "sy"), sighting_status("ANNOUNCED")),
        (date(2024, 9, 20), "المولد النبوي (التاريخ الشيعي، 17 ربيع الأول)", ("iq", "ir"),
         sighting_status("ANNOUNCED")),
    ),
    2025: (
        (date(2025, 1, 27), "المبعث النبوي / الإسراء والمعراج", ("iq", "ir", "jo", "lb", "sy"),
         sighting_status("ANNOUNCED")),
        (date(2025, 3, 30), "عيد الفطر (اليوم الأول)", ("iq", "jo", "lb", "sy"),
         sighting_status("ANNOUNCED")),
        (date(2025, 3, 31), "عيد الفطر (إيران والمرجعية في النجف، بعد يوم)", ("ir", "iq"),
         sighting_status("ANNOUNCED -- THE ONE-DAY SPLIT")),
        (date(2025, 4, 1), "عيد الفطر (اليوم الثاني)", ("iq", "jo", "lb", "sy"),
         sighting_status("ANNOUNCED")),
        (date(2025, 6, 5), "يوم عرفة", ("iq", "jo"), sighting_status("ANNOUNCED")),
        (date(2025, 6, 6), "عيد الأضحى (اليوم الأول)", ("iq", "jo", "lb", "sy"),
         sighting_status("ANNOUNCED")),
        (date(2025, 6, 7), "عيد الأضحى (إيران، بعد يوم)", ("ir", "iq"),
         sighting_status("ANNOUNCED -- THE ONE-DAY SPLIT")),
        (date(2025, 6, 8), "عيد الأضحى (اليوم الثاني)", ("iq", "jo", "lb", "sy"),
         sighting_status("ANNOUNCED")),
        (date(2025, 6, 14), "عيد الغدير", ("iq", "ir"), sighting_status("ANNOUNCED")),
        (date(2025, 6, 26), "رأس السنة الهجرية", ("iq", "ir", "jo", "lb", "sy"),
         sighting_status("ANNOUNCED")),
        (date(2025, 7, 5), "تاسوعاء", ("iq", "ir"), sighting_status("ANNOUNCED")),
        (date(2025, 7, 6), "عاشوراء", ("iq", "ir", "lb", "sy"), sighting_status("ANNOUNCED")),
        (date(2025, 8, 14), "الأربعين", ("iq", "ir"), sighting_status("ANNOUNCED")),
        (date(2025, 9, 4), "المولد النبوي (التاريخ السني)", ("iq", "jo", "lb", "sy"),
         sighting_status("ANNOUNCED")),
        (date(2025, 9, 9), "المولد النبوي (التاريخ الشيعي)", ("iq", "ir"),
         sighting_status("ANNOUNCED")),
    ),
    2026: (
        (date(2026, 1, 16), "المبعث النبوي / الإسراء والمعراج", ("iq", "ir", "jo", "lb", "sy"),
         sighting_status("PROJECTED")),
        (date(2026, 3, 20), "عيد الفطر (اليوم الأول) — متوقع", ("iq", "jo", "lb", "sy"),
         sighting_status("PROJECTED")),
        (date(2026, 3, 21), "عيد الفطر (إيران) — متوقع، ويصادف نوروز", ("ir", "iq"),
         sighting_status("PROJECTED -- AND IT FALLS ON NOWRUZ")),
        (date(2026, 3, 22), "عيد الفطر (اليوم الثاني) — متوقع", ("iq", "jo", "lb", "sy"),
         sighting_status("PROJECTED")),
        (date(2026, 5, 26), "يوم عرفة — متوقع", ("iq", "jo"), sighting_status("PROJECTED")),
        (date(2026, 5, 27), "عيد الأضحى (اليوم الأول) — متوقع", ("iq", "ir", "jo", "lb", "sy"),
         sighting_status("PROJECTED")),
        (date(2026, 5, 28), "عيد الأضحى (اليوم الثاني) — متوقع", ("iq", "ir", "jo", "lb", "sy"),
         sighting_status("PROJECTED")),
        (date(2026, 6, 4), "عيد الغدير — متوقع", ("iq", "ir"), sighting_status("PROJECTED")),
        (date(2026, 6, 16), "رأس السنة الهجرية — متوقع", ("iq", "ir", "jo", "lb", "sy"),
         sighting_status("PROJECTED")),
        (date(2026, 6, 25), "عاشوراء — متوقع", ("iq", "ir", "lb", "sy"),
         sighting_status("PROJECTED")),
        (date(2026, 8, 3), "الأربعين — متوقع", ("iq", "ir"), sighting_status("PROJECTED")),
        (date(2026, 8, 25), "المولد النبوي (التاريخ السني) — متوقع", ("iq", "jo", "lb", "sy"),
         sighting_status("PROJECTED")),
        (date(2026, 8, 30), "المولد النبوي (التاريخ الشيعي) — متوقع", ("iq", "ir"),
         sighting_status("PROJECTED")),
    ),
}

#: RAMADAN, WHICH IS A LIQUIDITY REGIME RATHER THAN A CLOSURE. Every one of the five shortens its
#: working day; the food-import and gold-retail seasons run inside it. (start, end, status).
RAMADAN_WINDOWS: dict[int, tuple[date, date, str]] = {
    2024: (date(2024, 3, 11), date(2024, 4, 9), "ANNOUNCED"),
    2025: (date(2025, 3, 1), date(2025, 3, 29), "ANNOUNCED"),
    2026: (date(2026, 2, 18), date(2026, 3, 19), "PROJECTED"),
}

# ------------------------------------------------------- the equinox, and the Solar Hijri year
#: MEEUS, ASTRONOMICAL ALGORITHMS, CHAPTER 27 -- the twenty-four periodic terms of the equinox
#: correction. Typing a Nowruz date into a table would be the one thing this pack must not do:
#: the Iranian year begins at the INSTANT of the March equinox as observed in Tehran, so the date
#: is 20 March in some years and 21 March in others, and the rule -- not the table -- is what
#: extends to 2027 and beyond. (A, B, C) with B and C in degrees.
_EQUINOX_TERMS: tuple[tuple[float, float, float], ...] = (
    (485.0, 324.96, 1934.136), (203.0, 337.23, 32964.467), (199.0, 342.08, 20.186),
    (182.0, 27.85, 445267.112), (156.0, 73.14, 45036.886), (136.0, 171.52, 22518.443),
    (77.0, 222.54, 65928.934), (74.0, 296.72, 3034.906), (70.0, 243.58, 9037.513),
    (58.0, 119.81, 33718.147), (52.0, 297.17, 150.678), (50.0, 21.02, 2281.226),
    (45.0, 247.54, 29929.562), (44.0, 325.15, 31555.956), (29.0, 60.93, 4443.417),
    (18.0, 155.12, 67555.328), (17.0, 288.79, 4562.452), (16.0, 198.04, 62894.029),
    (14.0, 199.76, 31436.921), (12.0, 95.39, 14577.848), (12.0, 287.11, 31931.756),
    (12.0, 320.81, 34777.259), (9.0, 227.73, 1222.114), (8.0, 15.45, 16859.074),
)
#: Tehran's civil offset. IRAN ABOLISHED DAYLIGHT SAVING IN 2022, so this is now constant, and
#: the Nowruz rule is applied against local civil noon.
TEHRAN_OFFSET_HOURS = 3.5
#: The twelve Solar Hijri months: six of 31 days, five of 30, then Esfand (29 or 30).
SOLAR_HIJRI_MONTH_LENGTHS: tuple[int, ...] = (31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29)


def march_equinox_utc(year: int) -> datetime:
    """The instant of the March equinox in UTC, to about a minute (Meeus ch. 27).

    Accurate enough for the only question asked of it -- whether the equinox falls before or
    after local noon in Tehran -- because the margin in the years this pack covers is measured in
    hours, not seconds. Delta-T is under two minutes across the sample and is ignored by name.
    """
    y = (int(year) - 2000) / 1000.0
    jde0 = (2451623.80984 + 365242.37404 * y + 0.05169 * y * y
            - 0.00411 * y ** 3 - 0.00057 * y ** 4)
    t = (jde0 - 2451545.0) / 36525.0
    w = math.radians(35999.373 * t - 2.47)
    delta_lambda = 1.0 + 0.0334 * math.cos(w) + 0.0007 * math.cos(2.0 * w)
    s = sum(a * math.cos(math.radians(b + c * t)) for a, b, c in _EQUINOX_TERMS)
    return _from_julian_day(jde0 + (0.00001 * s) / delta_lambda)


def _from_julian_day(jd: float) -> datetime:
    """A Julian Day number as a timezone-aware UTC datetime (Meeus ch. 7)."""
    z = math.floor(jd + 0.5)
    frac = (jd + 0.5) - z
    if z < 2299161:
        a = z
    else:
        alpha = math.floor((z - 1867216.25) / 36524.25)
        a = z + 1 + alpha - math.floor(alpha / 4)
    b = a + 1524
    c = math.floor((b - 122.1) / 365.25)
    d = math.floor(365.25 * c)
    e = math.floor((b - d) / 30.6001)
    day = b - d - math.floor(30.6001 * e) + frac
    month = int(e - 1) if e < 14 else int(e - 13)
    year = int(c - 4716) if month > 2 else int(c - 4715)
    whole = int(day)
    return (datetime(year, month, whole, tzinfo=UTC)
            + timedelta(days=float(day) - whole))


def nowruz(year: int) -> date:
    """1 Farvardin in a given Gregorian year, DERIVED from the equinox and never typed.

    THE RULE: the Iranian year begins on the day whose start precedes the equinox, which in
    practice means -- take the equinox instant, convert it to Tehran civil time, and if it falls
    BEFORE local noon that date is 1 Farvardin, otherwise the next date is. That produces
    2024-03-20, 2025-03-21 and 2026-03-21, which is what Iran actually observed.
    """
    tehran = march_equinox_utc(year) + timedelta(hours=TEHRAN_OFFSET_HOURS)
    return tehran.date() if tehran.hour < 12 else (tehran + timedelta(days=1)).date()


def solar_hijri_year(day: date) -> int:
    """The Solar Hijri year a Gregorian date falls in, derived from the same rule.

    The boundary is Nowruz, not 1 January and not 21 March: 2025-03-20 is still 1403 and
    2025-03-21 is 1404, because the 2025 equinox landed after Tehran noon.
    """
    return day.year - 621 if day >= nowruz(day.year) else day.year - 622


def iran_fiscal_year_start(sh_year: int) -> date:
    """The first day of an Iranian fiscal year, named by its Solar Hijri number.

    The budget, the FX allocation quotas and the subsidy envelope all break here. Because the
    boundary is derived rather than fixed at 21 March, a Gregorian quarter dummy cannot absorb it
    and a study that assumes 21 March is wrong in roughly half the years.
    """
    return nowruz(int(sh_year) + 621)


def solar_hijri_to_gregorian(sh_year: int, month: int, day_of_month: int) -> date:
    """A Solar Hijri date as a Gregorian one, counted forward from that year's derived Nowruz."""
    if not 1 <= int(month) <= 12:
        raise ValueError(f"solar hijri month {month!r} is out of range")
    offset = sum(SOLAR_HIJRI_MONTH_LENGTHS[: int(month) - 1]) + int(day_of_month) - 1
    return iran_fiscal_year_start(sh_year) + timedelta(days=offset)


def iran_national(year: int) -> dict[date, str]:
    """Iran's national closures in a Gregorian year, EVERY ONE DERIVED from the equinox.

    Nowruz 1-4 Farvardin, Islamic Republic Day on 12 Farvardin, Sizdah Bedar on 13 Farvardin,
    the Nationalisation of the Oil Industry on 29 Esfand (the day before Nowruz), the Revolution
    anniversary on 22 Bahman and the two Khordad days. The practical shutdown runs about thirteen
    days from Nowruz to Sizdah Bedar and it is the largest recurring demand gap in this pack.
    """
    start = nowruz(year)
    out: dict[date, str] = {}
    for i in range(4):
        out[start + timedelta(days=i)] = f"نوروز (روز {i + 1} فروردین)"
    out[start + timedelta(days=11)] = "روز جمهوری اسلامی (12 Farvardin)"
    out[start + timedelta(days=12)] = "سیزده بدر (13 Farvardin) — پایان تعطیلات نوروز"
    out[start - timedelta(days=1)] = "ملی شدن صنعت نفت (29 Esfand)"
    out[start + timedelta(days=75)] = "رحلت امام خمینی (14 Khordad)"
    out[start + timedelta(days=76)] = "قیام 15 خرداد (Khordad uprising)"
    revolution = nowruz(year - 1) + timedelta(days=327)
    if revolution.year == year:
        out[revolution] = "پیروزی انقلاب اسلامی (22 Bahman)"
    return {d: n for d, n in out.items() if d.year == year}


# --------------------------------------------------------------- the two Easters, both computed
def western_easter(year: int) -> date:
    """Gregorian Easter (the anonymous Gregorian computus). Lebanon observes it."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month, day = divmod(h + ell - 7 * m + 114, 31)
    return date(year, month, day + 1)


def orthodox_easter(year: int) -> date:
    """Julian (Orthodox) Easter expressed in the Gregorian calendar (Meeus' Julian computus plus
    the 13-day offset that holds for 1900-2099).

    LEBANON IS THE ONLY STATE IN THIS PACK THAT OBSERVES BOTH, and the gap between them is not a
    constant: it was 35 days in 2024, ZERO in 2025 when the two computi coincided, and 7 days in
    2026. A Lebanese seasonality study that models "Easter" as one date is modelling two
    different weeks in two years out of three.
    """
    a = year % 4
    b = year % 7
    c = year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month, day = divmod(d + e + 114, 31)
    return date(year, month, day + 1) + timedelta(days=13)


def lebanese_christian_days(year: int) -> dict[date, str]:
    """The movable Christian closures Lebanon keeps: both Good Fridays and both Easter Mondays."""
    west = western_easter(year)
    east = orthodox_easter(year)
    out: dict[date, str] = {
        west - timedelta(days=2): "الجمعة العظيمة (التقويم الغربي)",
        west + timedelta(days=1): "اثنين الفصح (التقويم الغربي)",
        east - timedelta(days=2): "الجمعة العظيمة (التقويم الشرقي)",
        east + timedelta(days=1): "اثنين الفصح (التقويم الشرقي)",
    }
    return {d: n for d, n in out.items() if d.year == year}


# --------------------------------------------------------------- the assembled holiday calendars
def fixed_national(cc: str, year: int) -> dict[date, str]:
    """One state's fixed solar days, with Syria's DATED calendar change applied."""
    out: dict[date, str] = {}
    for month, day, name in FIXED_NATIONAL.get(cc, ()):
        out[date(year, month, day)] = name
    if cc == "sy":
        rows = (SYRIA_PRE_TRANSITION if year <= SYRIA_CALENDAR_BREAK.year
                else SYRIA_POST_TRANSITION)
        for month, day, name in rows:
            out[date(year, month, day)] = name
    return out


def holidays_for(cc: str, year: int) -> dict[date, str]:
    """One state's whole closure calendar for a year: fixed, derived and sighted together."""
    key = str(cc).strip().lower()
    if key not in JURISDICTIONS:
        raise ValueError(f"{cc!r} is not one of {list(JURISDICTIONS)}")
    out: dict[date, str] = dict(fixed_national(key, year))
    if key == "ir":
        out.update(iran_national(year))
    if key == "lb":
        out.update(lebanese_christian_days(year))
    for day, name, states, _status in LUNAR_HOLIDAYS.get(year, ()):
        if key in states:
            out[day] = name
    return dict(sorted(out.items()))


def national_holidays(year: int) -> dict[date, str]:
    """The UNION across all five states: every day on which at least one of them is closed."""
    out: dict[date, str] = {}
    for cc in JURISDICTIONS:
        for day, name in holidays_for(cc, year).items():
            if day in out and cc.upper() not in out[day]:
                out[day] = f"{out[day]} | {cc.upper()}: {name}"
            else:
                out[day] = f"{cc.upper()}: {name}"
    return dict(sorted(out.items()))


def is_session_day(cc: str, day: date) -> bool:
    """True when that state's own cash market is open: not its weekend and not its holiday."""
    key = str(cc).strip().lower()
    if key not in JURISDICTIONS:
        raise ValueError(f"{cc!r} is not one of {list(JURISDICTIONS)}")
    if day.weekday() in WEEKENDS[key]:
        return False
    return day not in holidays_for(key, day.year)


def common_session_weekdays() -> tuple[int, ...]:
    """The weekdays on which ALL FIVE are open, DERIVED from the four weekend regimes.

    It is Monday, Tuesday and Wednesday, and it is derived rather than asserted because the
    answer is the point: Lebanon's Saturday-Sunday weekend and Iran's Thursday-Friday weekend are
    disjoint, so four of the seven days lose at least one of the five markets.
    """
    closed = {wd for pair in WEEKENDS.values() for wd in pair}
    return tuple(wd for wd in range(7) if wd not in closed)


def common_session_days(start: date, end: date) -> list[date]:
    """Every day in a range on which all five states' cash markets are open at once."""
    out: list[date] = []
    day = start
    while day <= end:
        if all(is_session_day(cc, day) for cc in JURISDICTIONS):
            out.append(day)
        day += timedelta(days=1)
    return out


def market_holidays(year: int) -> dict[date, str]:
    """The session-costing closures: a holiday that falls on a day that state would have traded.

    A national day that lands on its own country's weekend costs nothing and is dropped here --
    and because the five keep FOUR DIFFERENT WEEKENDS, the same Gregorian date can be
    session-costing in Beirut and free in Tehran.
    """
    out: dict[date, str] = {}
    for cc in JURISDICTIONS:
        for day, name in holidays_for(cc, year).items():
            if day.weekday() in WEEKENDS[cc]:
                continue
            prefix = f"{out[day]} | " if day in out else ""
            out[day] = f"{prefix}{cc.upper()}: {name}"
    return dict(sorted(out.items()))


def ramadan_window(year: int) -> tuple[date, date, str] | None:
    """The Ramadan window for a year, or None when the pack does not carry one."""
    return RAMADAN_WINDOWS.get(year)


def in_ramadan(day: date) -> bool:
    window = RAMADAN_WINDOWS.get(day.year)
    return bool(window and window[0] <= day <= window[1])


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "derived_solar_and_equinox_days_plus_two_computi_plus_typed_sightings",
    "authority": "five states and SEVEN announcing authorities: Iraq's Sunni and Shia endowment "
                 "diwans and the Najaf marja'iyya, Iran's Office of the Supreme Leader, Jordan's "
                 "Iftaa' Department, Lebanon's Dar al-Fatwa AND Higher Islamic Shia Council, and "
                 "Syria's Ministry of Awqaf",
    "rule": "FOUR KINDS OF DAY AND THEY ARE TREATED DIFFERENTLY ON PURPOSE. (1) THE FIXED SOLAR "
            "DAYS ARE DERIVED from month-day rules: Iraqi Army Day 6 January, Republic Day 14 "
            "July, Independence Day 3 October and Victory Day 10 December; Jordanian "
            "Independence Day 25 May; Lebanon's Saint Maroun 9 February, the Annunciation 25 "
            "March -- a holiday shared by Christians and Muslims and unique to Lebanon -- "
            "Martyrs' Day 6 May, Independence 22 November; Syria's Evacuation Day 17 April. "
            "(2) THE IRANIAN CALENDAR IS SOLAR HIJRI AND IS COMPUTED FROM THE MARCH EQUINOX. "
            "Nowruz is 1 Farvardin, the day on which the equinox falls before local noon in "
            "Tehran, which makes it 20 March in some years and 21 March in others; the country "
            "closes for roughly thirteen days to Sizdah Bedar on 13 Farvardin; the FISCAL YEAR "
            "begins on the same derived day; 22 Bahman, 14 and 15 Khordad and 29 Esfand are all "
            "derived from it by day-count. NOTHING IRANIAN IS TYPED. (3) LEBANON OBSERVES BOTH "
            "COMPUTI: Western and Orthodox Easter are each computed, and the gap between them "
            "was 35 days in 2024, ZERO in 2025 and 7 days in 2026. (4) THE ISLAMIC FEASTS "
            "CANNOT BE COMPUTED AND ARE NOT: Eid al-Fitr, Eid al-Adha, Arafat, the Hijri New "
            "Year, Ashura, Arbaeen, Ghadir and the two Mawlid dates are fixed by a SIGHTING "
            "announced the evening before, so they are TYPED for 2024, 2025 and 2026 with every "
            "row's status naming all five states' authorities. Iran and the Najaf marja'iyya "
            "routinely announce a DAY LATER than the Sunni authorities, and 2025 carries that "
            "split explicitly. THE WEEKENDS ARE FOUR: Iraq, Jordan and Syria rest Friday and "
            "Saturday (weekday 4 and 5), LEBANON RESTS SATURDAY AND SUNDAY (5 and 6) like a "
            "European market, and IRAN RESTS THURSDAY AND FRIDAY (3 and 4). Lebanon's weekend "
            "and Iran's are disjoint, so the only days all five are open are Monday, Tuesday and "
            "Wednesday -- `common_session_weekdays` derives that. There is NO weekend "
            "substitution anywhere in the five.",
    "years": (2024, 2025, 2026),
    "weekend": "iq/jo/sy Friday-Saturday (4,5); lb Saturday-Sunday (5,6); ir Thursday-Friday (3,4)",
    "weekends_by_country": {cc: WEEKENDS[cc] for cc in JURISDICTIONS},
    "common_session_weekdays": (0, 1, 2),
    "national_rule": "`national_holidays(year)` is the union across the five and "
                     "`holidays_for(code, year)` is one state's own calendar",
    "market_rule": "`market_holidays(year)` keeps only the closures that cost that state a "
                   "session, which is a different set for each of the four weekend regimes",
    "moon_sighting_rule": "DECLARED, not inferred. ANNOUNCED rows are what the committees "
                          "announced; PROJECTED rows may be a day off. Iraq and Lebanon each "
                          "carry TWO authorities, and a Saudi or Gulf calendar is the wrong "
                          "calendar for the Shia feasts that close Iraq and Iran for days",
    "moving_feasts": "the lunar feasts drift about eleven days earlier each solar year while the "
                     "Iranian solar calendar does not drift at all, so the two systems slide "
                     "past each other -- in 2026 Eid al-Fitr and Nowruz fall within a day of "
                     "each other and Iran loses both calendars' holidays in one window",
    "ramadan_rule": "all five shorten the working day for the month; the closure is Eid but the "
                    "liquidity change is the month, see RAMADAN_WINDOWS",
    "arbaeen_rule": "ARBAEEN IS THE LARGEST ANNUAL GATHERING ON EARTH and it closes Iraq for "
                    "days around Karbala; no Gulf or Levantine calendar contains it, and a "
                    "pooled MENA holiday dummy misses the single biggest Iraqi demand event",
    "table": {y: {d.isoformat(): n for d, n in national_holidays(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {
        2024: sighting_status("ANNOUNCED for every lunar row; the solar and derived days certain"),
        2025: sighting_status("ANNOUNCED for every lunar row, including the one-day Iranian "
                              "and Najaf split on Eid al-Fitr and Eid al-Adha"),
        2026: sighting_status("PROJECTED for every lunar row -- no 2026 sighting has happened; "
                              "the equinox-derived Iranian days and the two computi are certain"),
    },
    "known_dates": {
        "2024-03-20": "Nowruz 1403, DERIVED: the equinox fell at 06:37 Tehran, before noon",
        "2025-03-21": "Nowruz 1404, DERIVED: the equinox fell at 12:32 Tehran, AFTER noon, so "
                      "the new year began the next day -- the case a typed table gets wrong",
        "2025-04-20": "Western and Orthodox Easter COINCIDE; Lebanon keeps one long weekend "
                      "instead of two",
        "2025-03-30": "Eid al-Fitr in Baghdad (Sunni), Amman, Beirut and Damascus",
        "2025-03-31": "Eid al-Fitr in Tehran and for the Najaf marja'iyya -- the one-day split",
        "2026-03-21": "Nowruz 1405 AND the projected Iranian Eid al-Fitr on the same day",
        "2025-12-08": "the first anniversary of the Syrian transition, added to the calendar "
                      "while 8 March and 6 October were dropped from it",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "per_country_fn": holidays_for,
    "nowruz_fn": nowruz,
    "fiscal_fn": iran_fiscal_year_start,
    "easter_fns": (western_easter, orthodox_easter),
    "session_day_fn": is_session_day,
    "ramadan_fn": ramadan_window,
}
# ------------------------------------------------------------------- the pack's own mechanisms
#: LEBANON'S OFFICIAL RATE AS A DATED STAIRCASE. Twenty-two years at one number, then two
#: administrative steps sixty times apart. Row: (effective date, rate, what happened).
LBP_OFFICIAL_LADDER: tuple[tuple[date, float, str], ...] = (
    (date(1997, 12, 22), 1507.5, "the peg is set and held for twenty-two years, defended with "
                                 "financial engineering rather than with a trade surplus"),
    (date(2023, 2, 1), 15000.0, "the official rate is devalued by about ninety per cent, "
                                "announced in January and effective 1 February 2023; the "
                                "customs rate and the bank accounting rates followed through "
                                "February and March, which is why some reporting dates the "
                                "devaluation to March"),
    (date(2023, 11, 1), 89500.0, "Banque du Liban adopts 89,500 as the official rate, aligning "
                                 "the state's books with the banknote market for the first time "
                                 "since the collapse began"),
)
#: THE DATED STAGES OF THE COLLAPSE, as markers a study conditions on rather than pools across.
LEBANON_COLLAPSE_MARKERS: tuple[tuple[date, str], ...] = (
    (date(2019, 10, 17), "the protests begin; the banks close and informal capital controls start"),
    (date(2020, 3, 7), "Lebanon defaults on its March 2020 eurobond -- the first sovereign "
                       "default in the country's history"),
    (date(2020, 8, 4), "the Beirut port explosion destroys the country's principal grain silos "
                       "and its largest import gateway"),
    (date(2021, 5, 1), "the Sayrafa platform rate begins operating as a third simultaneous price"),
    (date(2023, 2, 1), "the official rate moves from 1,507.5 to 15,000"),
    (date(2023, 11, 1), "the official rate moves to 89,500 and Sayrafa is wound down"),
)
#: THE KURDISTAN-CEYHAN PIPELINE. Row: (effective date, state, approximate kb/d, evidence label).
#: The shutdown is the cleanest dated supply experiment in the pack, and the restart is carried
#: as REPORTED rather than as a number the desk has measured.
KURDISTAN_PIPELINE: tuple[tuple[date, str, float, str], ...] = (
    (date(2014, 1, 1), "FLOWING", 450.0, "PUBLIC_REPORTING: independent KRG exports through the "
                                         "Iraq-Turkey pipeline to Ceyhan, disputed by Baghdad "
                                         "throughout and litigated at the ICC from 2014"),
    (date(2023, 3, 25), "SHUT", 0.0, "PUBLISHED_RULING: the ICC arbitration award against Turkey "
                                     "is issued and Turkey halts pumping; roughly 450 kb/d "
                                     "leaves the market on a dated legal act"),
    (date(2025, 9, 27), "PARTIAL_RESUMPTION", 190.0, "PUBLIC_REPORTING: exports resume at a "
                                                     "reduced rate under a Baghdad-Erbil-company "
                                                     "arrangement; the volume is REPORTED and is "
                                                     "not a series this desk has measured"),
)
#: IRAQ'S PUBLISHED OPEC+ COMPENSATION PROMISES. Row: (announced, the window it covers, the
#: pledged cut in kb/d, status). A DATED PROMISE TO UNDER-PRODUCE is a commitment with a
#: measurable outcome, which is a different and much better object than a forecast.
IRAQ_COMPENSATION: tuple[tuple[date, str, float, str], ...] = (
    (date(2024, 4, 22), "2024-05 to 2024-09", 123.0, "PUBLISHED: the first detailed Iraqi "
                                                     "compensation schedule filed with the "
                                                     "Secretariat after sustained over-production"),
    (date(2024, 9, 5), "2024-10 to 2025-09", 166.0, "PUBLISHED: the schedule is extended and "
                                                    "re-tabled as the unwind is delayed"),
    (date(2025, 4, 12), "2025-05 to 2026-06", 120.0, "PUBLISHED: a further re-tabling as the "
                                                     "eight voluntary producers begin unwinding"),
)
#: THE DATED US ADMINISTRATIVE ACTS THAT SET IRANIAN OUTPUT. Every one is published in Washington
#: and none of them is a forecast. Row: (date, act, the direction it pushed exports).
IRAN_SANCTIONS_ACTS: tuple[tuple[date, str, str], ...] = (
    (date(2015, 7, 14), "the JCPOA is agreed in Vienna", "+"),
    (date(2016, 1, 16), "Implementation Day: nuclear-related sanctions are lifted and Iranian "
                        "exports recover toward 2.5 mb/d within a year", "+"),
    (date(2018, 5, 8), "the United States withdraws from the JCPOA and announces the "
                       "re-imposition of sanctions on a published wind-down schedule", "-"),
    (date(2018, 11, 5), "the oil sanctions snap back with 180-day Significant Reduction "
                        "Exceptions granted to eight buyers", "-"),
    (date(2019, 5, 2), "the waivers are allowed to EXPIRE; Indian and several other buyers stop "
                       "lifting and exports fall to a few hundred thousand barrels a day", "-"),
    (date(2021, 1, 20), "an administration change begins a period of reduced enforcement; "
                        "exports recover through 2022-2023 largely into Chinese independent "
                        "refiners", "+"),
    (date(2023, 9, 18), "a prisoner-and-funds arrangement marks the high point of the informal "
                        "accommodation", "+"),
    (date(2025, 2, 4), "enforcement is tightened again under a renewed maximum-pressure policy "
                       "with designations targeting the shadow-fleet logistics", "-"),
)


def lbp_official_rate(day: date) -> dict[str, Any]:
    """The Lebanese OFFICIAL rate on a given day, with the act that set it.

    MECHANISM ONE. A Lebanese series that carries one exchange rate across 2023 is carrying three
    different administered numbers under one label; this function says which one was in force and
    names the act, so a cell can condition on the step rather than pool across it.
    """
    chosen = LBP_OFFICIAL_LADDER[0]
    for row in LBP_OFFICIAL_LADDER:
        if day >= row[0]:
            chosen = row
    held_days = (day - chosen[0]).days
    return {"date": day.isoformat(), "official": float(chosen[1]),
            "effective_from": chosen[0].isoformat(), "held_days": held_days,
            "why": str(chosen[2]),
            "regime": "PEG_HELD" if chosen[1] == 1507.5 else "POST_DEVALUATION"}


def parallel_premium(currency: str, official: float, parallel: float) -> dict[str, Any]:
    """The premium of a parallel-market rate over its administered rate, and what that means.

    MECHANISM TWO, and the one this pack is built on. Three of the five currencies have two or
    more simultaneous prices; the PREMIUM is the instrument, not the level. A currency the pack
    does not carry, or a non-positive rate, returns UNMEASURED by name rather than a number
    (L1.28a) -- and JOD returns a premium of zero by construction, which is exactly why it is
    the control.
    """
    ccy = str(currency).strip().upper()
    row = CURRENCIES.get(ccy)
    if row is None:
        return {"currency": ccy, "measured": False, "premium_pct": None,
                "why": f"UNMEASURED: {ccy} is not one of {sorted(CURRENCIES)}"}
    if official <= 0 or parallel <= 0:
        return {"currency": ccy, "measured": False, "premium_pct": None,
                "why": "UNMEASURED: a non-positive rate is not a rate"}
    premium = (float(parallel) / float(official) - 1.0) * 100.0
    if premium < 1.0:
        state = "NO_PREMIUM"
    elif premium < 25.0:
        state = "FRICTION"
    elif premium < 200.0:
        state = "STRESS"
    else:
        state = "REGIME_FAILURE"
    return {"currency": ccy, "measured": True, "premium_pct": round(premium, 4),
            "state": state, "regime": str(row["regime"]),
            "jurisdiction": str(row["jurisdiction"]),
            "why": "the premium is a COMPLIANCE-FRICTION term before it is a devaluation "
                   "expectation; separating the two is the work, and the JOD control pins the "
                   "zero end of the scale because its official and market rates are one number"}


def kurdistan_pipeline_state(day: date) -> dict[str, Any]:
    """The Iraq-Turkey pipeline's state on a given day, and the volume it was carrying.

    MECHANISM THREE. The 2023-03-25 halt is a dated, published LEGAL act that removed roughly
    450 kb/d from the seaborne market, which is about as clean a supply-shock natural experiment
    as crude offers. The 2025 partial resumption is carried as REPORTED, never as measured.
    """
    chosen = KURDISTAN_PIPELINE[0]
    for row in KURDISTAN_PIPELINE:
        if day >= row[0]:
            chosen = row
    return {"date": day.isoformat(), "state": str(chosen[1]), "kbd": float(chosen[2]),
            "since": chosen[0].isoformat(), "evidence": str(chosen[3]),
            "shut": chosen[1] == "SHUT",
            "why": "an ICC arbitration award against Turkey, not a production decision; the "
                   "control is Iraqi FEDERAL exports through Basrah over the same window, which "
                   "separates 'Iraqi supply' from 'this pipeline'"}


def iran_policy_direction(day: date) -> dict[str, Any]:
    """Which published US administrative act was last in force, and which way it pushed exports.

    MECHANISM FOUR. Iranian production is not a geological variable over this sample: it is a
    function of dated acts published in the Federal Register and by OFAC. This returns the act,
    never a barrel count, because the barrel count is exactly what the two OPEC series disagree
    about.
    """
    chosen: tuple[date, str, str] | None = None
    for row in IRAN_SANCTIONS_ACTS:
        if day >= row[0]:
            chosen = row
    if chosen is None:
        return {"date": day.isoformat(), "measured": False, "direction": "",
                "why": "UNMEASURED: the act table begins at the 2015 JCPOA and this day precedes "
                       "it; the pre-2015 sanctions history is real and is not carried here"}
    return {"date": day.isoformat(), "measured": True, "act": chosen[1],
            "act_date": chosen[0].isoformat(), "direction": chosen[2],
            "why": "the ACT is the event and it is published in Washington on a known day; the "
                   "production response is the thing being measured and is never assumed"}


def iraq_compensation_due(day: date) -> dict[str, Any]:
    """The Iraqi OPEC+ compensation schedule in force on a day, if any.

    MECHANISM FIVE. A published promise to under-produce by a named volume in named months is a
    commitment with a measurable outcome. The falsifier is built in: if realised Iraqi exports do
    not fall in the pledged window, the promise was not a constraint, and that is a finding.
    """
    live = [row for row in IRAQ_COMPENSATION if day >= row[0]]
    if not live:
        return {"date": day.isoformat(), "measured": False, "pledged_kbd": None,
                "why": "UNMEASURED: no compensation schedule had been published by this date"}
    chosen = live[-1]
    return {"date": day.isoformat(), "measured": True, "announced": chosen[0].isoformat(),
            "window": str(chosen[1]), "pledged_kbd": float(chosen[2]), "status": str(chosen[3]),
            "why": "compliance is measured against the PUBLISHED schedule and against the "
                   "monthly export volumes the Oil Ministry itself prints, not against a "
                   "third-party estimate"}


def coin_premium(coin_price: float, gold_price: float, coin_grams: float = 7.3224,
                 purity: float = 0.900) -> dict[str, Any]:
    """The Bahar Azadi coin's premium over its own metal content -- a pure expectations term.

    MECHANISM SIX. The full-size Bahar Azadi carries 7.3224 g at 900 thousandths. Given the coin's
    quoted local price and the local gold price for the same weight basis, the residual is what
    Iranian households are paying for the OPTION to hold hard value, and it is quoted publicly
    every day. An input of zero or less returns UNMEASURED rather than a ratio.
    """
    if coin_price <= 0 or gold_price <= 0 or coin_grams <= 0:
        return {"measured": False, "premium_pct": None,
                "why": "UNMEASURED: a non-positive price or weight is not a price"}
    intrinsic = float(gold_price) * float(coin_grams) * float(purity)
    premium = (float(coin_price) / intrinsic - 1.0) * 100.0
    return {"measured": True, "intrinsic": round(intrinsic, 6),
            "premium_pct": round(premium, 4),
            "why": "the premium (حباب) is the expectations term; it widens when the free-market "
                   "rial weakens and when domestic inflation expectations rise, and it is "
                   "reported daily by the Persian financial press"}


# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "Amman Stock Exchange daily foreign-investor buy/sell statistics",
     "root": "https://www.ase.com.jo/en/trading-statistics",
     "fields": ("foreign_buy", "foreign_sell", "net_foreign_jod", "arab_vs_non_arab",
                "foreign_ownership_pct"),
     "frequency": "daily", "snapshot": "each session", "publish_utc": "11:00", "lag_days": 0,
     "licence": "free, public", "available": True,
     "why": "THE CLEANEST LOCAL FLOW SERIES IN THE PACK. The ASE splits every session into Arab "
            "and non-Arab, resident and non-resident; because the marginal holder is Gulf money, "
            "the net non-resident line is a regional-risk gauge and not only a Jordanian one",
     "pit_warning": "published with the session, so it is point-in-time; it is the CASH market's "
                    "flow and says nothing about the currency, which does not move"},
    {"name": "Central Bank of Iraq daily auction allocation and compliance rejection share",
     "root": "https://cbi.iq/currency_auction",
     "fields": ("allocated_usd", "cash_vs_transfer", "rejected_share", "official_rate"),
     "frequency": "daily", "snapshot": "each business day", "publish_utc": "08:00", "lag_days": 0,
     "licence": "free, public", "available": True,
     "why": "the volume the state actually converted and the share refused on compliance grounds; "
            "together they are the supply side of the parallel premium and both are same-day",
     "pit_warning": "the page OVERWRITES IN PLACE, so the point-in-time history exists only in "
                    "the archive layer's crawls; an un-archived month is UNMEASURED, not assumed"},
    {"name": "Tehran Stock Exchange retail account and flow statistics",
     "root": "https://www.tse.ir", "fields": ("retail_net", "institutional_net", "index_rial",
                                              "traded_value"),
     "frequency": "daily", "snapshot": "each session", "publish_utc": "09:30", "lag_days": 0,
     "licence": "free, public", "available": True,
     "why": "one of the largest retail equity ecologies in the region by account count; the "
            "retail net line is a domestic inflation-hedging gauge, because Iranians rotate "
            "between equities, coins and dollars rather than between equities and bonds",
     "pit_warning": "THE INDEX IS QUOTED IN RIALS. A nominal rise during a devaluation is a "
                    "currency fact, and any real-terms reading must deflate by the FREE rate, "
                    "not the official one"},
    {"name": "Banque du Liban weekly balance sheet (the reserve and gold lines)",
     "root": "https://www.bdl.gov.lb/statisticsandresearch",
     "fields": ("fx_reserves", "gold_holdings", "currency_in_circulation", "claims_on_state"),
     "frequency": "weekly", "snapshot": "mid-month and month-end", "publish_utc": "12:00",
     "lag_days": 5, "licence": "free, public", "available": True,
     "why": "LEBANON'S GOLD HOLDING IS AMONG THE LARGEST PER CAPITA IN THE WORLD and it was never "
            "sold through the collapse; the reserve line is what the banknote rate trades against",
     "pit_warning": "definitions changed during the crisis and several lines were restated; a "
                    "vintage read is mandatory and a current-vintage series is not point-in-time"},
    {"name": "COT or exchange-traded positioning for IQD, IRR, JOD, LBP or SYP",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: none of the five currencies has a futures contract on any exchange "
            "the desk can read, and no COT line exists for any of them",
     "pit_warning": "DOES NOT EXIST. Positioning in these five is UNMEASURED by name and is "
                    "never proxied by the dollar index: one of the five is the dollar by "
                    "construction and the other four are administered, so a USD position is not "
                    "a position in any of them"},
    {"name": "Iraq Stock Exchange intraday tape and order book",
     "root": "http://www.isx-iq.net", "fields": (), "frequency": "n/a", "snapshot": "",
     "publish_utc": "", "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: the ISX publishes daily summaries and no machine-readable intraday "
            "tape; there is no public depth, no public trade print and no listed derivative",
     "pit_warning": "DOES NOT EXIST. Every Iraqi equity mechanism in this pack terminates in "
                    "crude, gold or the lira legs and the ISX is an OBSERVABLE only"},
    {"name": "Syrian market, trade and monetary statistics",
     "root": "https://cb.gov.sy", "fields": (), "frequency": "n/a", "snapshot": "",
     "publish_utc": "", "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT AND DATED: the Central Bureau of Statistics' regular publication "
            "largely stopped after 2011-2012, the IMF has not completed an Article IV "
            "consultation since before the war, and the 2024-12-08 transition changed the "
            "publishing institutions themselves",
     "pit_warning": "DOES NOT EXIST IN A USABLE FORM. The LAWFUL SUBSTITUTE is MIRROR DATA -- UN "
                    "Comtrade and the Turkish, Chinese, Jordanian and Lebanese customs portals "
                    "reporting their own trade WITH Syria -- plus FAO/GIEWS crop assessments and "
                    "WFP priced food baskets. A Syrian claim cites the mirror or it is UNMEASURED"},
)
# --------------------------------------------------------------------------- terminology
#: FOUR LANGUAGES AND THE PACK MEANS ALL FOUR. Arabic is the language of the decrees, the
#: gazettes and the presses of four of the five states. PERSIAN is the language of everything
#: Iranian and is NOT Arabic: a crawler that searches Arabic on an Iranian ground finds nothing.
#: KURDISH -- Sorani in the Arabic script and Kurmanji in the Latin one -- is the language in
#: which the Kurdistan Regional Government publishes its OWN oil and budget positions, and those
#: positions DIFFER FROM BAGHDAD'S, which is itself the observable. English and French carry the
#: prospectuses, the arbitration record, the IMF documents and half the Lebanese press.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "OPECN-A": ("شركة تسويق النفط العراقية", "سومو", "أسعار البيع الرسمية", "خام البصرة المتوسط",
                "خام البصرة الثقيل", "الفروق السعرية", "وزارة النفط العراقية", "الصادرات النفطية",
                "معدل السعر المتحقق", "SOMO official selling price", "Basrah Medium",
                "Basrah Heavy", "Asia differential", "monthly lifting programme"),
    "OPECN-B": ("خط أنابيب كركوك جيهان", "إقليم كردستان", "وزارة الثروات الطبيعية",
                "التحكيم الدولي", "غرفة التجارة الدولية", "إيقاف الضخ", "بۆری نەوتی کەرکووک", "هەناردەی نەوت", "وەزارەتی سامانە سروشتییەکان",
                "هەرێمی کوردستان", "نەوت و گاز", "Herêma Kurdistanê", "boriya neftê",
                "Kirkuk-Ceyhan pipeline", "ICC arbitration award", "KRG oil exports",
                "pipeline shut-in"),
    "OPECN-C": ("أوبك بلس", "حصة الإنتاج", "جدول التعويض", "الالتزام بالخفض", "الإنتاج الفائض",
                "اللجنة الوزارية المشتركة", "إعلان التعاون", "OPEC+ compensation schedule",
                "quota compliance", "over-production", "JMMC", "voluntary adjustment"),
    "OPECN-D": ("البنك المركزي العراقي", "مزاد العملة", "نافذة بيع الدولار", "السوق الموازية",
                "سعر الصرف الرسمي", "فرق السعر", "حوالات الدولار", "منصة التحويلات",
                "الامتثال المصرفي", "Iraqi dinar parallel rate", "CBI dollar auction",
                "transfer compliance platform", "dinar revaluation"),
    "OPECN-E": ("تحریم نفتی", "برجام", "صادرات نفت ایران", "وزارت نفت", "شرکت ملی نفت ایران",
                "معافیت تحریمی", "فروش نفت", "پالایشگاه", "گزارش تحریم",
                "العقوبات الأمريكية", "JCPOA",
                "OFAC designation", "sanctions waiver expiry", "maximum pressure",
                "Federal Register notice"),
    "OPECN-F": ("تولید نفت ایران", "آمار اوپک", "گزارش ماهانه اوپک", "منابع ثانویه",
                "ارتباط مستقیم",
                "المصادر الثانوية", "الاتصال المباشر", "direct communication",
                "secondary sources", "OPEC MOMR production table", "series divergence",
                "reported versus estimated output"),
    "OPECN-G": ("نرخ ارز آزاد", "دلار بازار آزاد", "سکه بهار آزادی", "حباب سکه", "بانک مرکزی",
                "نرخ رسمی ارز", "سامانه نیما", "گواهی سپرده سکه", "قیمت گرمی طلا",
                "Bahar Azadi coin premium",
                "free-market rial", "NIMA rate", "coin bubble"),
    "OPECN-H": ("پارس جنوبی", "ناترازی گاز", "قطعی برق", "مازوت", "مصرف گاز خانگی",
                "صنایع انرژی‌بر", "نیروگاه برق", "South Pars", "winter gas deficit",
                "power shortfall", "fuel switching", "industrial curtailment"),
    "OPECN-I": ("البنك المركزي الأردني", "سعر الصرف الثابت", "الدينار الأردني",
                "برنامج صندوق النقد الدولي", "الاحتياطيات الأجنبية", "ميناء العقبة",
                "التسهيل الائتماني الممدد", "Jordanian dinar peg", "0.709 parity",
                "IMF Extended Fund Facility", "reserve adequacy", "peg that held"),
    "OPECN-J": ("شركة البوتاس العربية", "شركة مناجم الفوسفات الأردنية", "البحر الميت", "الأسمدة",
                "صادرات البوتاس", "صخر الفوسفات", "كلوريد البوتاسيوم", "Arab Potash",
                "Dead Sea potash", "phosphate rock", "fertiliser cost", "MOP contract price"),
    "OPECN-K": ("مصرف لبنان", "منصة صيرفة", "سعر السوق الموازي", "الليرة اللبنانية",
                "التعثر عن السداد", "سندات اليوروبوند", "الكابيتال كونترول", "سعر المنصة",
                "Banque du Liban", "taux parallèle", "Sayrafa", "eurobond default", "lollar",
                "banknote rate", "peg failure"),
    "OPECN-L": ("القمح", "مرفأ بيروت", "إهراءات القمح", "الطحين", "الدعم الحكومي",
                "استيراد القمح", "المخزون الاستراتيجي", "Beirut port silos",
                "wheat import dependence", "flour subsidy", "strategic grain reserve"),
    "OPECN-M": ("المكتب المركزي للإحصاء", "البيانات الرسمية", "إحصاءات مرآة", "التجارة الخارجية",
                "منظمة الأغذية والزراعة", "برنامج الأغذية العالمي", "تقدير المحصول",
                "mirror statistics", "UN Comtrade", "FAO crop assessment", "WFP market monitor",
                "partner-reported trade"),
    "OPECN-N": ("مصرف سورية المركزي", "الليرة السورية", "السوق السوداء", "سعر الحوالات",
                "تعدد أسعار الصرف", "المرحلة الانتقالية", "Syrian pound multiple rates",
                "remittance rate", "the 2024 transition", "discontinuous series"),
    "OPECN-O": ("مضيق هرمز", "الملاحة البحرية", "التأمين البحري", "ناقلات النفط", "أمن الطاقة",
                "تنگه هرمز", "بیمه کشتی", "گذرگاه هرمز", "Strait of Hormuz", "war-risk premium",
                "tanker insurance", "transit chokepoint", "freight rate"),
    "OPECN-P": ("خط الغاز العربي", "الربط الكهربائي", "الغاز المصري", "شركة الكهرباء الوطنية",
                "محطة دير علي", "استجرار الغاز", "Arab Gas Pipeline", "Egypt-Jordan gas",
                "electricity interconnection", "gas swap arrangement"),
    "OPECN-Q": ("التحويلات المالية", "المغتربون", "الاغتراب", "حوالات العاملين", "سوق العمل",
                "شركات الصرافة", "remittance corridor", "expatriate transfers", "diaspora flows",
                "Gulf labour market"),
    "OPECN-R": ("اللاجئون", "المفوضية السامية لشؤون اللاجئين", "خطة الاستجابة", "الأعباء المالية",
                "النزوح", "المساعدات الإنسانية", "refugee response plan", "UNHCR appeal",
                "EU-Turkey statement", "fiscal burden of displacement"),
}

#: The ENGLISH working vocabulary the pack must ALSO carry: the arbitration record, the OFAC
#: notices, the IMF documents and the fertiliser trade press are written in it, and an
#: Arabic-and-Persian-only crawl of this region misses the award that shut the pipeline.
ENGLISH_MARKERS: tuple[str, ...] = (
    "SOMO official selling price", "Basrah Heavy", "ICC arbitration award", "KRG oil exports",
    "OPEC+ compensation schedule", "CBI dollar auction", "OFAC designation",
    "sanctions waiver expiry", "direct communication", "secondary sources",
    "Bahar Azadi coin premium", "IMF Extended Fund Facility", "Dead Sea potash", "Sayrafa",
    "eurobond default", "Beirut port silos", "mirror statistics", "Strait of Hormuz",
    "Arab Gas Pipeline", "remittance corridor",
)

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

#: The Arabic script blocks, which carry Arabic, Persian AND Sorani Kurdish.
_ARABIC_RANGES = ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF), (0xFB50, 0xFDFF),
                  (0xFE70, 0xFEFF))
#: The four letters Persian adds to the Arabic alphabet. A pack that carries Arabic and calls
#: Iran covered has read the wrong language: `پ چ ژ گ` are the cheapest possible proof that a
#: Persian query is really Persian and not an Arabic transliteration of an Iranian subject.
_PERSIAN_LETTERS = frozenset("پچژگ")
#: The letters Sorani Kurdish adds. The KRG publishes its oil and budget positions in these.
_KURDISH_LETTERS = frozenset("ڕڵێۆھ")


def has_arabic(text: str) -> bool:
    """True when the text contains at least one Arabic-script codepoint (Arabic, Persian or
    Sorani Kurdish all qualify -- they share the script)."""
    return any(any(lo <= ord(ch) <= hi for lo, hi in _ARABIC_RANGES) for ch in str(text))


def has_persian(text: str) -> bool:
    """True when the text carries a letter Persian has and Arabic does not."""
    return any(ch in _PERSIAN_LETTERS for ch in str(text))


def has_kurdish(text: str) -> bool:
    """True when the text carries a letter Sorani Kurdish has and Arabic does not."""
    return any(ch in _KURDISH_LETTERS for ch in str(text))


def arabic_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return [t for terms in rows.values() for t in terms if has_arabic(t)]


def persian_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return [t for terms in rows.values() for t in terms if has_persian(t)]


def kurdish_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return [t for terms in rows.values() for t in terms if has_kurdish(t)]


def english_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    """Every declared English marker actually present in the terminology table."""
    rows = TERMINOLOGY if terminology is None else terminology
    flat = {t for terms in rows.values() for t in terms}
    return [m for m in ENGLISH_MARKERS if any(m in t for t in flat)]


def term_count(terminology: Mapping[str, Iterable[str]] | None = None) -> int:
    rows = TERMINOLOGY if terminology is None else terminology
    return len({t for terms in rows.values() for t in terms})


def _seq(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(str(v) for v in values)


def source_class(sid: str, label: str, *, layer: str, roots: Iterable[str],
                 queries: Iterable[str], languages: Iterable[str], access_label: str,
                 credibility: str, predictive_state: str, licence: str,
                 jurisdictions: Iterable[str] = (), machine_use_allowed: bool = True,
                 notes: str = "") -> dict[str, Any]:
    """One class of source with the roots a crawler starts from and its three INDEPENDENT labels.

    `queries` carry the native script, never only a translation. `machine_use_allowed=False`
    registers ground whose terms forbid extraction: never scraped, never omitted.
    """
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
            "jurisdictions": _seq(jurisdictions), "access_label": access_label,
            "credibility": credibility, "predictive_state": predictive_state,
            "machine_use_allowed": bool(machine_use_allowed), "licence": licence, "notes": notes}


def absent_layer(layer: str, jurisdiction: str, reason: str, substitute: str) -> dict[str, Any]:
    """A layer ONE JURISDICTION has nothing in, declared BY NAME with the reason AND the lawful
    substitute that carries the information instead.

    This is the shape the brief asks for and the shape L1.28a asks for: a blank layer and an
    absent layer look identical in a table and mean opposite things. Because this pack answers
    for five states, the absence is scoped to the state that has it -- Syria has no domestic
    academic economics; Jordan does -- so the row is `absent_<layer>_<cc>` and a real source in
    the same layer from another state still counts for the layer.
    """
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"absent layer {layer!r}")
    if jurisdiction not in JURISDICTIONS:
        raise ValueError(f"absent layer {layer!r}: {jurisdiction!r} is not a jurisdiction here")
    return {"id": f"absent_{layer}_{jurisdiction}",
            "label": f"NO SOURCE IN THIS LAYER: {layer} ({jurisdiction})", "layer": layer,
            "jurisdictions": (jurisdiction,), "roots": (), "queries": (), "languages": (),
            "access_label": "ACCESS_UNCLEAR", "credibility": "UNKNOWN",
            "predictive_state": "UNTESTED", "machine_use_allowed": False, "licence": "n/a",
            "reason": reason, "substitute": substitute,
            "notes": f"DECLARED ABSENT, NOT BLANK: {reason} | LAWFUL SUBSTITUTE: {substitute}"}
SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    # ---- official
    source_class(
        "opecn_iq_official", "Iraq: the central bank, the statistics office, the Oil Ministry, "
                             "SOMO and the official gazette", layer="official",
        roots=("https://cbi.iq", "https://cosit.gov.iq", "https://oil.gov.iq",
               "https://somooil.gov.iq"),
        queries=("البنك المركزي العراقي مزاد العملة", "نشرة أسعار الصرف", "الجهاز المركزي للإحصاء",
                 "وزارة النفط الصادرات النفطية الشهرية", "شركة تسويق النفط أسعار البيع الرسمية",
                 "خام البصرة المتوسط", "الموازنة العامة الاتحادية", "الوقائع العراقية",
                 "الإيرادات النفطية", "CBI daily auction result", "SOMO OSP announcement",
                 "monthly crude export report"),
        languages=("ar", "en"), jurisdictions=("iq",), access_label="OPEN_DATA",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="THE MOST TRANSPARENT OIL PUBLISHER IN OPEC AFTER OMAN: the Oil Ministry prints "
              "monthly export VOLUME and REVENUE, so the realised average price is computable, "
              "and SOMO announces the Basrah differentials on a dated monthly cycle"),
    source_class(
        "opecn_krg_official", "Iraqi Kurdistan: the KRG and its Ministry of Natural Resources, "
                              "which publish IN KURDISH AND ENGLISH and DISAGREE WITH BAGHDAD",
        layer="official",
        roots=("https://gov.krd", "http://mnr.krg.org"),
        queries=("هەرێمی کوردستان بودجە", "وەزارەتی سامانە سروشتییەکان", "هەناردەی نەوت",
                 "بۆری نەوتی کەرکووک جەیهان", "ڕێککەوتنی بەغدا و هەولێر",
                 "حكومة إقليم كردستان الموازنة", "صادرات نفط الإقليم",
                 "KRG oil export statement", "Ministry of Natural Resources monthly report",
                 "Herêma Kurdistanê petrol"),
        languages=("ku", "ar", "en"), jurisdictions=("iq",), access_label="OPEN_DATA",
        credibility="RELIABLE", predictive_state="UNTESTED", licence="free, public",
        notes="TWO GOVERNMENTS PUBLISH TWO DIFFERENT NUMBERS FOR THE SAME BARRELS, and the GAP "
              "is the observable rather than a nuisance -- it is the live state of the "
              "Baghdad-Erbil dispute that the ICC award and the pipeline shutdown turn on"),
    source_class(
        "opecn_ir_official", "Iran: Bank Markazi, the Statistical Centre, the oil ministry's "
                             "news agency SHANA and the Majlis legal database", layer="official",
        roots=("https://www.cbi.ir", "https://www.amar.org.ir", "https://www.shana.ir",
               "https://rc.majlis.ir"),
        queries=("بانک مرکزی نرخ ارز", "سامانه نیما", "شاخص بهای کالاها و خدمات مصرفی",
                 "مرکز آمار ایران", "وزارت نفت اخبار", "پارس جنوبی تولید گاز",
                 "بودجه سال مالی", "قانون بودجه مجلس", "صادرات نفت خام",
                 "Bank Markazi exchange rate table", "SHANA gas production", "Majlis budget law"),
        languages=("fa", "en"), jurisdictions=("ir",), access_label="PUBLIC",
        credibility="RELIABLE", predictive_state="UNTESTED", licence="free, public",
        notes="READING A PUBLISHED STATISTIC IS NOT A TRANSACTION. Everything here is a public "
              "government page; nothing is credentialled, nothing is a sanctioned entity's "
              "private system, and the desk never trades an Iranian instrument -- see "
              "ACCESS_CONSTRAINTS"),
    source_class(
        "opecn_jo_official", "Jordan: the central bank, the Department of Statistics, the "
                             "Ministry of Finance and the Official Gazette", layer="official",
        roots=("https://www.cbj.gov.jo", "https://dos.gov.jo", "https://www.mof.gov.jo"),
        queries=("البنك المركزي الأردني النشرة الإحصائية", "الاحتياطيات الأجنبية",
                 "دائرة الإحصاءات العامة الرقم القياسي", "التجارة الخارجية الأردنية",
                 "وزارة المالية النشرة المالية", "الدين العام", "الجريدة الرسمية الأردنية",
                 "أسعار الفائدة", "صادرات البوتاس والفوسفات",
                 "CBJ monthly statistical bulletin", "Jordan Department of Statistics CPI"),
        languages=("ar", "en"), jurisdictions=("jo",), access_label="OPEN_DATA",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="THE ONLY COMPLETE, UNINTERRUPTED, INTERNATIONALLY RECONCILED STATISTICAL SERIES "
              "IN THE PACK, which is precisely what makes Jordan usable as the control for the "
              "other four rather than merely as a fifth country"),
    source_class(
        "opecn_lb_official", "Lebanon: Banque du Liban, the Central Administration of Statistics "
                             "and the Ministry of Finance", layer="official",
        roots=("https://www.bdl.gov.lb", "http://www.cas.gov.lb",
               "https://www.finance.gov.lb"),
        queries=("مصرف لبنان الميزانية الأسبوعية", "احتياطي العملات الأجنبية", "منصة صيرفة",
                 "إدارة الإحصاء المركزي مؤشر الأسعار", "وزارة المالية الدين العام",
                 "سعر الصرف الرسمي", "تعميم مصرف لبنان", "Banque du Liban weekly balance sheet",
                 "Sayrafa platform rate", "Lebanon official exchange rate circular"),
        languages=("ar", "fr", "en"), jurisdictions=("lb",), access_label="PUBLIC",
        credibility="RELIABLE", predictive_state="UNTESTED", licence="free, public",
        notes="THE BDL BALANCE SHEET IS THE MOST-READ DOCUMENT IN LEBANESE ECONOMICS and it kept "
              "publishing through the collapse; the CAS consumer-price series, by contrast, had "
              "gaps during the worst of it and its vintages must be read rather than assumed"),
    source_class(
        "opecn_sy_official", "Syria: the Central Bank of Syria and the surviving statistical "
                             "listings -- REGISTERED WITH THEIR CREDIBILITY LABELLED",
        layer="official",
        roots=("https://cb.gov.sy",),
        queries=("مصرف سورية المركزي نشرة أسعار الصرف", "سعر صرف الحوالات",
                 "المكتب المركزي للإحصاء", "المجموعة الإحصائية السنوية", "التجارة الخارجية سورية",
                 "قرار مجلس النقد والتسليف", "Central Bank of Syria exchange rate bulletin"),
        languages=("ar", "en"), jurisdictions=("sy",), access_label="ACCESS_UNCLEAR",
        credibility="UNRELIABLE", predictive_state="UNTESTED", licence="unclear",
        notes="LABELLED HONESTLY AND KEPT AT LOW WEIGHT RATHER THAN DROPPED. Regular statistical "
              "publication largely stopped after 2011-2012; the exchange-rate bulletin continued "
              "intermittently; the 2024-12-08 transition changed the publishing institutions. A "
              "source that is unreliable is still a dated claim and is kept as evidence, never "
              "used as a series"),
    # ---- institutional
    source_class(
        "opecn_opec_iea_eia", "OPEC's Monthly Oil Market Report, the IEA's public releases and "
                              "the EIA's country and chokepoint analyses", layer="institutional",
        roots=("https://www.opec.org/opec_web/en/publications/338.htm",
               "https://www.iea.org/topics/oil-market-report",
               "https://www.eia.gov/international/analysis"),
        queries=("تقرير أوبك الشهري", "إنتاج النفط حسب الدولة", "المصادر الثانوية",
                 "گزارش ماهانه اوپک", "تولید نفت ایران بر اساس منابع ثانویه",
                 "OPEC MOMR crude production direct communication", "secondary sources table",
                 "EIA Strait of Hormuz transit volumes", "IEA oil market report Iran supply"),
        languages=("en", "ar", "fa"), jurisdictions=("iq", "ir"), access_label="PUBLIC",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="THE ONE SOURCE THAT PUBLISHES TWO CONTRADICTORY NUMBERS FOR IRAN ON PURPOSE, "
              "monthly, with the same cover date -- direct communication and secondary sources. "
              "The GAP is the observable and it is free"),
    source_class(
        "opecn_imf_un", "IMF Article IV reports and statistics, World Bank MENA updates, UN "
                        "Comtrade, UNHCR and OCHA response plans, ESCWA", layer="institutional",
        roots=("https://www.imf.org/en/Countries", "https://comtradeplus.un.org",
               "https://data.unhcr.org", "https://www.worldbank.org/en/region/mena"),
        queries=("تقرير المادة الرابعة صندوق النقد", "برنامج التسهيل الائتماني الممدد الأردن",
                 "خطة الاستجابة للأزمة السورية", "المفوضية السامية لشؤون اللاجئين تمويل",
                 "گزارش صندوق بین‌المللی پول ایران", "IMF Article IV Jordan",
                 "UN Comtrade partner reported imports Syria", "UNHCR Syria regional response",
                 "World Bank Lebanon Economic Monitor"),
        languages=("en", "ar", "fa"), jurisdictions=("iq", "ir", "jo", "lb", "sy"),
        access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
        licence="free, public",
        notes="COMTRADE IS THE MIRROR GROUND: what Syria and Iran do not publish, their partners "
              "report. UNHCR's funding tracker dates the refugee-driven fiscal shocks that this "
              "pack treats as events rather than as background"),
    source_class(
        "opecn_exchanges", "The five national exchanges and their regulators: ISX, TSE and IFB, "
                           "ASE, BSE, DSE", layer="institutional",
        roots=("http://www.isx-iq.net", "https://www.tse.ir", "https://www.ase.com.jo",
               "https://www.bse.com.lb"),
        queries=("سوق العراق للأوراق المالية النشرة اليومية", "بورصة عمان تداولات غير الأردنيين",
                 "بورصة بيروت", "بورس اوراق بهادار تهران شاخص کل",
                 "ارزش معاملات خرد", "Amman Stock Exchange foreign investor statistics",
                 "Tehran Stock Exchange total index", "ISX daily bulletin"),
        languages=("ar", "fa", "en"), jurisdictions=("iq", "ir", "jo", "lb"),
        access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED",
        licence="free, public",
        notes="NO CFD QUOTES ANY OF THEM and three publish no machine-readable tape, so they are "
              "OBSERVABLES. The ASE's daily foreign-investor split is the one genuinely useful "
              "flow series; the TSE's retail statistics are the one genuinely large retail ground"),
    # ---- academic
    source_class(
        "opecn_academic", "Regional and diaspora academic economics: AUB and LAU (Beirut), the "
                          "University of Jordan, Iraqi and Iranian university repositories, and "
                          "the open indexes", layer="academic",
        roots=("https://openalex.org", "https://core.ac.uk", "https://www.aub.edu.lb/ifi",
               "https://ganj.irandoc.ac.ir"),
        queries=("انهيار سعر الصرف في لبنان دراسة", "السياسة النقدية العراقية بحث",
                 "الربط بالدولار والاحتياطيات دراسة", "أثر اللجوء على المالية العامة",
                 "تورم و نرخ ارز مقاله", "اثر تحریم بر اقتصاد ایران",
                 "Lebanon currency crisis working paper", "Iraq dollar auction literature",
                 "Jordan peg sustainability study", "sanctions and oil exports estimation"),
        languages=("ar", "fa", "en", "fr"), jurisdictions=("iq", "ir", "jo", "lb"),
        access_label="OPEN_DATA", credibility="RELIABLE", predictive_state="UNTESTED",
        licence="open access where indexed",
        notes="IRANDOC AND THE IRANIAN UNIVERSITY REPOSITORIES ARE A REAL AND LARGELY UNREAD "
              "GROUND: Persian-language theses on inflation, the coin premium and the FX lattice "
              "are indexed and public, and no English-only crawl reaches any of them"),
    source_class(
        "opecn_think_tanks", "Policy institutes that publish dated, sourced regional economics: "
                             "Chatham House, Carnegie Middle East, the Iraq Energy Institute, "
                             "Bourse and Bazaar", layer="academic",
        roots=("https://www.chathamhouse.org/regions/middle-east-and-north-africa",
               "https://carnegie-mec.org", "https://www.bourseandbazaar.com"),
        queries=("تقرير عن الاقتصاد العراقي", "دراسة عن أزمة الكهرباء في العراق",
                 "تحلیل اقتصاد ایران گزارش", "سیاست ارزی ایران تحلیل",
                 "Iraq electricity and gas import dependence report",
                 "Iran petrochemical revenue analysis", "Lebanon banking restructuring paper"),
        languages=("en", "ar", "fa"), jurisdictions=("iq", "ir", "lb"),
        access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED",
        licence="free, public",
        notes="kept in the ACADEMIC layer rather than the media one because the output is "
              "sourced and dated; where a paper is advocacy it is labelled and down-weighted "
              "rather than dropped, because an advocacy paper is still a dated, testable claim"),
    # ---- practitioner
    source_class(
        "opecn_practitioner", "Specialist trade reporting a practitioner actually reads: Iraq "
                              "Oil Report, Amwaj.media, Executive Magazine, Argus and Platts "
                              "public headlines", layer="practitioner",
        roots=("https://www.iraqoilreport.com", "https://amwaj.media",
               "https://www.executive-magazine.com"),
        queries=("تقرير نفط العراق", "صادرات كردستان تقرير", "تحليل سوق النفط العراقي",
                 "تحلیل بازار نفت ایران", "Iraq Oil Report export figures",
                 "Amwaj Iraq dinar analysis", "Executive Magazine Lebanon banking",
                 "Basrah OSP commentary"),
        languages=("en", "ar", "fa"), jurisdictions=("iq", "lb"),
        access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE", predictive_state="UNTESTED",
        licence="subscription for the body; headlines and summaries public",
        machine_use_allowed=False,
        notes="REGISTERED AND NEVER SCRAPED. Iraq Oil Report is the best single practitioner "
              "ground on Iraqi and Kurdish exports and its terms do not permit machine "
              "extraction, so it is recorded here as ground that EXISTS and the pack measures on "
              "the ministry's own published figures instead. Omitting it would lose the knowledge"),
    source_class(
        "opecn_fertiliser_trade", "The fertiliser and commodity trade press that prices potash "
                                  "and phosphate: Argus Media public releases, CRU headlines, "
                                  "Profercy and the producers' own announcements",
        layer="practitioner",
        roots=("https://www.argusmedia.com/en/fertilizer", "https://www.arabpotash.com"),
        queries=("أسعار البوتاس العقود السنوية", "شركة البوتاس العربية نتائج",
                 "صادرات الفوسفات الأردني", "potash contract settlement India China",
                 "phosphate rock price index", "Arab Potash annual production"),
        languages=("ar", "en"), jurisdictions=("jo",), access_label="PUBLIC_WITH_TERMS",
        credibility="RELIABLE", predictive_state="UNTESTED",
        licence="headline and producer releases public; the assessments are licensed",
        machine_use_allowed=False,
        notes="THE ASSESSMENTS THEMSELVES ARE LICENSED and are registered, never fetched. The "
              "producer's own published production and export tonnages are free and are what "
              "the fertiliser-cost route into CORN and WHEAT is actually built on"),
    # ---- retail_ecology
    source_class(
        "opecn_retail_rates", "The parallel-rate tracking culture: Iraqi and Lebanese exchange "
                              "rate trackers, the Tehran coin and free-market quote pages",
        layer="retail_ecology",
        roots=("https://lirarate.org", "https://www.tgju.org"),
        queries=("سعر صرف الدولار اليوم في بغداد", "سعر الدولار في السوق الموازي لبنان",
                 "سعر صرف الليرة اللبنانية اليوم", "سعر الدولار في أربيل",
                 "قیمت دلار آزاد امروز", "قیمت سکه بهار آزادی", "حباب سکه امروز",
                 "نرخ طلای آب شده", "Lebanon parallel rate tracker", "Baghdad dollar rate today"),
        languages=("ar", "fa", "en"), jurisdictions=("iq", "ir", "lb"),
        access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE", predictive_state="UNTESTED",
        licence="free, public; crowd- and dealer-sourced",
        notes="KEPT AT LOW WEIGHT AND NEVER DROPPED. These pages are where the PARALLEL RATE and "
              "the COIN PREMIUM are actually quoted, because no central bank publishes them. "
              "They are dealer- and crowd-sourced and therefore UNRELIABLE as a label -- which "
              "is a measurement of the ground, not a reason to pretend the ground is not there"),
    source_class(
        "opecn_retail_forums", "The domestic retail investment ecology: Iranian equity and coin "
                               "forums and channels, Iraqi and Jordanian investment groups",
        layer="retail_ecology",
        roots=("https://www.sahamyab.com", "https://www.tgju.org/forum"),
        queries=("تحلیل بورس تهران انجمن", "خرید سکه یا دلار", "سرمایه گذاری در طلا ایران",
                 "منتدى الاستثمار في بورصة عمان", "شراء الذهب في العراق",
                 "Tehran bourse retail sentiment", "gold versus dollar Iran retail"),
        languages=("fa", "ar", "en"), jurisdictions=("ir", "iq", "jo"),
        access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE", predictive_state="UNTESTED",
        licence="free, public",
        notes="IRAN IS THE ONLY STATE IN THIS PACK WITH A LARGE DOMESTIC RETAIL TRADING ECOLOGY, "
              "because its population cannot reach an international broker and rotates between "
              "equities, coins and dollars instead. That rotation is the mechanism OPECN-G is "
              "built on and this is where it is discussed"),
    # ---- app_ecosystem
    source_class(
        "opecn_payments", "The domestic payment and transfer rails that publish volumes: Iraq's "
                          "e-payment and card schemes, Jordan's CliQ and eFAWATEERcom, Lebanon's "
                          "transfer operators, Iran's Shaparak", layer="app_ecosystem",
        roots=("https://cbi.iq", "https://www.jopacc.com", "https://www.shaparak.ir"),
        queries=("إحصاءات الدفع الإلكتروني العراق", "بطاقات الدفع المحلية",
                 "نظام كليك الأردن حجم التحويلات", "إي فواتيركم إحصاءات",
                 "آمار تراکنش شاپرک", "مبلغ تراکنش‌های کارتی",
                 "JoPACC CliQ transaction volumes", "Shaparak monthly transaction report"),
        languages=("ar", "fa", "en"), jurisdictions=("iq", "ir", "jo"),
        access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED",
        licence="free, public",
        notes="SHAPARAK PUBLISHES IRANIAN CARD TRANSACTION VALUE MONTHLY, which is a nominal "
              "spending series in a high-inflation economy and therefore a real-time inflation "
              "proxy where no timely CPI exists; JoPACC's CliQ volumes do the same job for Jordan"),
    source_class(
        "opecn_remittance_apps", "The remittance corridor's own pricing: the World Bank's "
                                 "Remittance Prices Worldwide database and the operators' "
                                 "published corridor rates", layer="app_ecosystem",
        roots=("https://remittanceprices.worldbank.org", "https://www.omtco.com"),
        queries=("أسعار الحوالات إلى لبنان", "تكلفة التحويل من الخليج إلى الأردن",
                 "شركات الصرافة أسعار الحوالات", "حواله به ایران هزینه",
                 "remittance prices Gulf to Lebanon corridor", "OMT exchange rate today"),
        languages=("ar", "fa", "en"), jurisdictions=("jo", "lb", "sy"),
        access_label="OPEN_DATA", credibility="RELIABLE", predictive_state="UNTESTED",
        licence="free, public",
        notes="THE CORRIDOR PRICE IS THE ONLY MACHINE-READABLE SYRIAN PRICE LEFT: the operators "
              "publish the rate at which a transfer is paid out, which is the rate a Syrian "
              "household actually faces and is not the central bank's official print"),
    # ---- media
    source_class(
        "opecn_media_arabic", "The Arabic regional and national press: Shafaq News, Rudaw, "
                              "Al-Monitor, An-Nahar, L'Orient-Le Jour, Jordan Times, Al-Mada",
        layer="media",
        roots=("https://shafaq.com", "https://www.rudaw.net", "https://www.al-monitor.com",
               "https://www.annahar.com", "https://www.lorientlejour.com",
               "https://jordantimes.com"),
        queries=("سعر صرف الدينار العراقي اليوم", "قرار مجلس الوزراء بشأن الدولار",
                 "اتفاق بغداد أربيل النفط", "أزمة الكهرباء والغاز الإيراني",
                 "ارتفاع سعر الدولار في لبنان", "قرار مصرف لبنان الجديد",
                 "هەواڵی نەوت", "Shafaq News dinar rate", "Rudaw KRG oil export",
                 "L'Orient-Le Jour taux de change"),
        languages=("ar", "ku", "fr", "en"), jurisdictions=("iq", "jo", "lb", "sy"),
        access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED",
        licence="free, public",
        notes="RUDAW AND SHAFAQ CARRY THE KURDISH SIDE OF EVERY IRAQI OIL STORY and frequently "
              "publish Erbil's figures before Baghdad confirms or denies them; L'Orient-Le Jour "
              "is the French-language Lebanese record and is not a translation of the Arabic"),
    source_class(
        "opecn_media_persian", "The Persian financial press and the state agencies: "
                               "Donya-e-Eqtesad, IRNA, Tasnim, Mehr, ISNA", layer="media",
        roots=("https://donya-e-eqtesad.com", "https://www.irna.ir", "https://www.tasnimnews.com",
               "https://www.mehrnews.com"),
        queries=("قیمت دلار در بازار آزاد", "نرخ سکه و طلا امروز", "بودجه سال آینده مجلس",
                 "صادرات نفت ایران آمار", "ناترازی انرژی زمستان", "تورم نقطه به نقطه",
                 "تحریم‌های جدید آمریکا", "Donya-e-Eqtesad dollar rate", "IRNA oil export"),
        languages=("fa", "en"), jurisdictions=("ir",), access_label="PUBLIC",
        credibility="UNRELIABLE", predictive_state="UNTESTED", licence="free, public",
        notes="KEPT AT LOW WEIGHT WITH ITS REASON NAMED: the state agencies are state agencies "
              "and Donya-e-Eqtesad is the serious financial daily, but all of them operate under "
              "editorial constraint. A constrained source is still a DATED CLAIM, and the coin "
              "and free-rate quotes it carries exist nowhere official at all"),
    # ---- archive
    source_class(
        "opecn_archive", "The gazettes and the crawl archive: al-Waqai al-Iraqiya, the Jordanian "
                         "Official Gazette, the Lebanese Official Gazette, the Internet Archive",
        layer="archive",
        roots=("https://web.archive.org", "https://moj.gov.iq", "https://www.pm.gov.jo"),
        queries=("الوقائع العراقية أعداد سابقة", "الجريدة الرسمية الأردنية أرشيف",
                 "الجريدة الرسمية اللبنانية مرسوم", "قرار مجلس الوزراء أرشيف",
                 "آرشیو روزنامه رسمی", "قانون بودجه سال‌های گذشته",
                 "wayback CBI auction page", "gazette archive decree exchange rate"),
        languages=("ar", "fa", "en"), jurisdictions=("iq", "ir", "jo", "lb"),
        access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
        licence="free, public",
        notes="THE ARCHIVE LAYER IS LOAD-BEARING HERE AND NOT DECORATIVE: the CBI auction page, "
              "the Lebanese official rate page and the Tehran quote pages ALL OVERWRITE IN "
              "PLACE, so the only point-in-time history of three of this pack's most important "
              "series is whatever a crawler captured at the time"),
    source_class(
        "opecn_archive_oil", "The dated oil record: OPEC's MOMR back issues, the ICC and court "
                             "filings, and the published arbitration record", layer="archive",
        roots=("https://www.opec.org/opec_web/en/publications/338.htm",
               "https://jusmundi.com", "https://www.italaw.com"),
        queries=("قرار التحكيم الدولي بشأن أنبوب كركوك", "الدعوى العراقية ضد تركيا",
                 "archive OPEC monthly oil market report 2019", "ICC arbitration Iraq Turkey "
                 "pipeline award", "Iraq Turkey Pipeline Agreement 1973 arbitration"),
        languages=("en", "ar"), jurisdictions=("iq",), access_label="PUBLIC_ARCHIVE",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="THE ARBITRATION RECORD IS THE SUPPLY SHOCK'S DOCUMENTATION. A published ruling "
              "with a date is what separates this event from an outage, and the back issues of "
              "the MOMR are how the two Iranian series' divergence is reconstructed historically"),
    # ---- physical_economy
    source_class(
        "opecn_ports_pipelines", "The physical plant: Basrah and Khor al-Amaya terminals, Umm "
                                 "Qasr and the Grand Faw port, Ceyhan, Aqaba, Beirut, Tartus and "
                                 "Latakia, and the Arab Gas Pipeline", layer="physical_economy",
        roots=("https://scp.gov.iq", "https://www.aqabaports.com.jo",
               "https://www.portdebeyrouth.com"),
        queries=("ميناء أم قصر حركة السفن", "ميناء الفاو الكبير", "الموانئ العراقية إحصاءات",
                 "ميناء العقبة حركة البضائع", "مرفأ بيروت إحصاءات", "خط الغاز العربي ضخ",
                 "طريق التنمية العراق", "بندر و اسکله صادرات", "Grand Faw port progress",
                 "Aqaba container throughput", "Ceyhan loadings"),
        languages=("ar", "fa", "en"), jurisdictions=("iq", "jo", "lb", "sy"),
        access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED",
        licence="free, public",
        notes="THE DEVELOPMENT ROAD AND THE GRAND FAW PORT ARE A DATED, FUNDED, PUBLISHED "
              "INFRASTRUCTURE PROGRAMME -- a Basrah-to-Turkey corridor whose milestones are "
              "announcements with dates, which is the same object shape as a capacity schedule"),
    source_class(
        "opecn_food_energy_physical", "The physical food and power economy: FAO/GIEWS crop "
                                      "assessments, WFP priced food baskets, and the published "
                                      "electricity and gas import figures",
        layer="physical_economy",
        roots=("https://www.fao.org/giews/countrybrief", "https://dataviz.vam.wfp.org",
               "https://www.ferc.gov"),
        queries=("تقدير محصول القمح في سورية", "الاستيراد الغذائي لبنان", "سلة الغذاء الأسعار",
                 "استجرار الغاز المصري للأردن", "أزمة الكهرباء في لبنان",
                 "واردات گاز و برق", "FAO GIEWS Syria wheat production",
                 "WFP Lebanon food basket price", "Jordan electricity imports gas"),
        languages=("ar", "fa", "en"), jurisdictions=("iq", "jo", "lb", "sy"),
        access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
        licence="free, public",
        notes="FAO/GIEWS AND WFP ARE THE ONLY SYSTEMATIC SYRIAN PRICE AND CROP SERIES LEFT and "
              "they are the named substitute for the absent national statistics; they are also "
              "the cleanest read on Lebanese import requirements after the silos were destroyed"),
    # ---- source_graph
    source_class(
        "opecn_mirror_customs", "MIRROR STATISTICS: the Chinese, Indian and Turkish customs "
                                "portals and UN Comtrade, read as the partners' own reports of "
                                "trade WITH these five", layer="source_graph",
        roots=("http://www.customs.gov.cn", "https://tradestat.commerce.gov.in",
               "https://data.tuik.gov.tr", "https://comtradeplus.un.org"),
        queries=("الصادرات التركية إلى سورية", "التبادل التجاري مع العراق",
                 "واردات الصين من النفط الخام حسب المصدر", "صادرات ایران به چین",
                 "آمار گمرک", "China customs crude imports by origin Malaysia",
                 "India DGCI&S imports from Iran", "TUIK Turkey exports to Syria",
                 "Comtrade partner reported Syria imports"),
        languages=("zh", "en", "ar", "fa", "tr"), jurisdictions=("ir", "iq", "sy"),
        access_label="OPEN_DATA", credibility="RELIABLE", predictive_state="UNTESTED",
        licence="free, public",
        notes="THE CENTRAL SUBSTITUTE OF THIS PACK. What Iran and Syria do not publish, their "
              "trading partners do. The Chinese crude line for 'Malaysia' is the standing "
              "example: the tonnage exceeds Malaysian production by a wide margin and the "
              "difference is the mirror's own statement about origin"),
    source_class(
        "opecn_citation_graph", "What the other nine layers cite: OFAC and Federal Register "
                                "citations, the arbitration record's own references, the "
                                "attribution language of the regional press", layer="source_graph",
        roots=("https://www.federalregister.gov", "https://ofac.treasury.gov",
               "https://sanctionssearch.ofac.treas.gov"),
        queries=("وفقا لمصادر مطلعة", "نقلا عن وكالة الأنباء الرسمية", "حسب بيان وزارة الخزانة",
                 "به نقل از منابع آگاه", "بر اساس اعلام وزارت خزانه‌داری",
                 "citing sources familiar with the matter", "Federal Register Iran general "
                 "license", "OFAC specially designated nationals list update"),
        languages=("en", "ar", "fa"), jurisdictions=("ir", "iq", "sy"),
        access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
        licence="free, public",
        notes="OFAC'S OWN PUBLISHED DESIGNATIONS AND GENERAL LICENCES ARE THE EVENT CLOCK, and "
              "they are a US government publication -- machine-readable, free and lawful to "
              "read. Following what the regional press cites is how a rumour is separated from "
              "a filing"),
    # ---- the declared absences: five for Syria, one for Iran, each with its substitute named
    absent_layer("academic", "sy",
                 "NO INDEPENDENT DOMESTIC ACADEMIC ECONOMICS SURVIVES. Syrian university "
                 "economics faculties have published no usable working-paper or data-bearing "
                 "literature since roughly 2012, and the IMF has completed no Article IV "
                 "consultation since before the war",
                 "the DIASPORA AND REGIONAL literature -- AUB's Issam Fares Institute, Chatham "
                 "House, the World Bank's MENA Economic Update and ESCWA -- indexed through "
                 "OpenAlex and CORE, read as literature ABOUT Syria rather than FROM it"),
    absent_layer("practitioner", "sy",
                 "NO PRACTITIONER RESEARCH GROUND EXISTS. No bank, broker or research house "
                 "publishes Syrian coverage; the specialist outlets that do cover the economy "
                 "are subscription-only and their terms forbid machine extraction",
                 "the humanitarian and conflict-economy analysts who publish openly -- ACAPS, "
                 "COAR, and the FAO/WFP assessments -- plus the Turkish and Jordanian trade "
                 "press reporting the border commerce from the other side"),
    absent_layer("retail_ecology", "sy",
                 "NO RETAIL TRADING ECOLOGY EXISTS. The Damascus Securities Exchange publishes "
                 "no machine-readable tape, there is no margin or retail FX regime, and dealing "
                 "in foreign currency has been criminalised at points in the sample, which "
                 "drives the ground that does exist out of public view",
                 "the REMITTANCE PRICING ground: the transfer operators' published payout rates "
                 "and the World Bank's Remittance Prices database, which is the rate a Syrian "
                 "household actually faces, plus WFP's governorate-level priced food basket"),
    absent_layer("app_ecosystem", "sy",
                 "NO DOMESTIC PAYMENT OR TRADING APPLICATION PUBLISHES STATISTICS, and "
                 "comprehensive sanctions exclude Syrian entities from the global app stores "
                 "and payment rails, so there is no volume series to read",
                 "UN agency CASH-TRANSFER reporting, which publishes the value and modality of "
                 "transfers delivered by governorate, and the remittance operators' corridor "
                 "pricing -- together these are the only machine-readable Syrian payment data"),
    absent_layer("institutional", "sy",
                 "NO FUNCTIONING INSTITUTIONAL STATISTICAL COUNTERPART. There has been no IMF "
                 "Article IV consultation since before the war, the Damascus Securities Exchange "
                 "publishes no tape, and no industry association or clearer publishes aggregates",
                 "MIRROR CUSTOMS from Turkey, Jordan, Lebanon and China plus UN Comtrade, and "
                 "the World Bank and ESCWA regional aggregates that still carry Syria as a memo "
                 "item -- partner-reported trade is the institutional record that survives"),
    absent_layer("practitioner", "ir",
                 "NO INTERNATIONAL SELL-SIDE OR BROKER RESEARCH ON IRAN LAWFULLY EXISTS. No bank "
                 "under US or EU jurisdiction publishes Iranian coverage under the sanctions "
                 "regime, so the practitioner ground a normal market has is simply not there",
                 "the DOMESTIC Persian-language analytical ground -- Donya-e-Eqtesad and the "
                 "Tehran Stock Exchange ecosystem's own analysis -- together with Amwaj.media "
                 "and the OPEC/IEA secondary-source tables, which are the outside world's "
                 "practitioner-grade estimates of the same quantities"),
)

#: NO LAYER IS BLANK PACK-WIDE: every one of the ten carries at least one crawlable source from
#: at least one of the five states. The absences above are JURISDICTION-SCOPED and that is the
#: honest shape -- Jordan has academic economics and Syria does not, and collapsing the two into
#: one "MENA academic layer" would hide exactly the fact the pack exists to record.
LAYER_ABSENCES: dict[str, str] = {}

#: WHERE THE GROUND GENUINELY DOES NOT EXIST, NAMED, WITH WHAT CARRIES THE INFORMATION INSTEAD.
#: Not a layer absence -- a SERIES absence, and each one bounds a domain rather than blocking it.
NO_LAWFUL_GROUND: tuple[dict[str, str], ...] = (
    {"what": "a continuous Syrian national accounts, CPI or trade series after about 2012",
     "why": "regular statistical publication largely stopped; the Central Bureau of Statistics' "
            "annual compendium became intermittent, the IMF has completed no Article IV since "
            "before the war, and the 2024-12-08 transition changed the publishing institutions",
     "consequence": "OPECN-M and OPECN-N are built on MIRROR CUSTOMS (Comtrade plus the Turkish, "
                    "Chinese, Jordanian and Lebanese portals), FAO/GIEWS crop assessments and "
                    "WFP priced food baskets; a Syrian claim cites the mirror or answers "
                    "UNMEASURED by name"},
    {"what": "an official Iranian export volume series",
     "why": "Iran does not publish its crude export volumes under sanctions, and the two series "
            "that do exist -- OPEC direct communication and OPEC secondary sources -- disagree "
            "by hundreds of thousands of barrels a day",
     "consequence": "OPECN-E and OPECN-F treat the DIVERGENCE as the observable and the "
                    "published US administrative acts as the event clock; no single export "
                    "number is ever asserted"},
    {"what": "the discount at which Iranian crude actually sells",
     "why": "the seller publishes nothing and the buyers' contract terms are private; every "
            "circulating figure is a third-party estimate from shipping and refinery reporting",
     "consequence": "the discount enters as a REPORTED low-credibility observable, and the "
                    "measurable leg is the mirror customs VALUE divided by VOLUME on the "
                    "partner side, which is an average realised price rather than a differential"},
    {"what": "a COT or exchange positioning series for IQD, IRR, JOD, LBP or SYP",
     "why": "no futures contract exists for any of the five on any exchange the desk can read",
     "consequence": "positioning in this pack is UNMEASURED by name and is never proxied by the "
                    "dollar index: one of the five IS the dollar by construction and the other "
                    "four are administered"},
    {"what": "an intraday tape for the ISX, the ASE, the BSE or the DSE",
     "why": "none of the four publishes a machine-readable intraday tape and no CFD is quoted on "
            "any of their indices",
     "consequence": "every equity mechanism here terminates in crude, gas, gold, the grain "
                    "complex or the lira and shekel legs; the local index is an OBSERVABLE"},
    {"what": "the Platts and Argus sour-crude and fertiliser assessments",
     "why": "licensed products whose terms forbid machine extraction; registered with "
            "machine_use_allowed=false and never fetched",
     "consequence": "OPECN-A and OPECN-J are measured on the exchange-traded crude legs, on the "
                    "producers' own published tonnages and on the grain complex instead"},
    {"what": "the Sayrafa platform's own transaction volumes and counterparty detail",
     "why": "Banque du Liban published the rate and not the book; the volumes were never "
            "disclosed in a form that can be reconstructed",
     "consequence": "OPECN-K conditions on the RATE REGIME in force -- peg, Sayrafa era, "
                    "post-devaluation -- and never on a platform volume series that does not "
                    "exist"},
    {"what": "a point-in-time history of the CBI auction page, the Lebanese official rate page "
             "and the Tehran quote pages",
     "why": "all three OVERWRITE IN PLACE and keep no history of their own",
     "consequence": "the only vintage record is the archive layer's crawls; a cell compiled on "
                    "an un-archived month is UNMEASURED rather than assumed"},
    {"what": "Iraqi federal and Kurdish production reconciled to one number",
     "why": "Baghdad and Erbil publish different figures for the same barrels and neither "
            "accepts the other's; the dispute is the reason the pipeline is shut",
     "consequence": "OPECN-B and OPECN-C carry BOTH numbers and treat the gap as the state "
                    "variable; a study that picks one has picked a side rather than a series"},
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


def declared_absences() -> tuple[dict[str, str], ...]:
    """Every jurisdiction-scoped layer absence, with its reason and its named substitute."""
    return tuple({"layer": str(sc["layer"]), "jurisdiction": str(sc["jurisdictions"][0]),
                  "reason": str(sc.get("reason") or ""),
                  "substitute": str(sc.get("substitute") or "")}
                 for sc in SOURCE_CLASSES if str(sc["id"]).startswith("absent_"))


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
            "declared_absences": declared_absences(),
            "no_lawful_ground": [row["what"] for row in NO_LAWFUL_GROUND],
            "rule": "ten layers, each carrying a source or named ABSENT with a reason AND a "
                    "lawful substitute; because this pack answers for five states the absence is "
                    "SCOPED TO THE STATE that has it, so Syria's missing academic ground is "
                    "recorded without pretending Jordan's is missing too; fringe and "
                    "state-constrained PUBLIC material is kept at low weight and never dropped; "
                    "a page whose terms forbid machine extraction is registered "
                    "machine_use_allowed=false, never scraped and never omitted; a series that "
                    "does not lawfully exist is named in NO_LAWFUL_GROUND with the domain it "
                    "bounds"}


#: NATIVE QUERY TERRITORIES: what the deep-forest miner actually types, per layer. Arabic for
#: four of the five states, PERSIAN for Iran, KURDISH for the KRG's own publications, French for
#: Lebanon and English for the arbitration, IMF and OFAC record. An English-only crawl of this
#: ground reads the English corner of it and reports the corner as the ground.
QUERY_TERRITORIES: dict[str, tuple[str, ...]] = {
    "official": ("سعر صرف الدينار العراقي الرسمي اليوم", "شركة تسويق النفط أسعار البيع الرسمية",
                 "وزارة النفط العراقية الصادرات الشهرية", "البنك المركزي الأردني النشرة الإحصائية",
                 "مصرف لبنان الميزانية الأسبوعية", "مصرف سورية المركزي نشرة أسعار الصرف",
                 "نرخ رسمی ارز بانک مرکزی", "بودجه سال مالی مجلس", "هەناردەی نەوتی هەرێم",
                 "CBI currency auction result", "SOMO Basrah Medium OSP"),
    "institutional": ("تقرير أوبك الشهري إنتاج العراق", "تقرير المادة الرابعة للأردن",
                      "بورصة عمان تداولات غير الأردنيين", "سوق العراق للأوراق المالية نشرة",
                      "گزارش ماهانه اوپک تولید ایران", "شاخص کل بورس تهران",
                      "OPEC MOMR secondary sources Iran", "IMF Article IV Lebanon",
                      "UN Comtrade Syria partner imports"),
    "academic": ("دراسة انهيار سعر الصرف في لبنان", "بحث السياسة النقدية العراقية",
                 "أثر اللجوء السوري على المالية العامة الأردنية", "دراسة الربط بالدولار",
                 "مقاله تورم و نرخ ارز", "پایان‌نامه اثر تحریم بر صادرات نفت",
                 "Lebanon peg collapse working paper", "Jordan dinar peg sustainability",
                 "Iraq dollar auction empirical study"),
    "practitioner": ("تقرير نفط العراق صادرات كردستان", "تحليل أسعار البيع الرسمية",
                     "تحليل السوق اللبناني المصرفي", "أسعار البوتاس العقود السنوية",
                     "تحلیل بازار ارز ایران", "گزارش تحلیلی بورس",
                     "Iraq Oil Report monthly exports", "Amwaj Iraq dinar platform",
                     "potash contract settlement"),
    "retail_ecology": ("سعر الدولار في السوق الموازي بغداد", "سعر صرف الليرة اللبنانية اليوم",
                       "سعر الدولار في أربيل اليوم", "شراء الذهب في العراق",
                       "قیمت دلار آزاد امروز", "قیمت سکه بهار آزادی و حباب",
                       "خرید سکه یا دلار کدام بهتر است", "Lebanon parallel rate today",
                       "Baghdad dollar exchange shops"),
    "app_ecosystem": ("إحصاءات الدفع الإلكتروني في العراق", "نظام كليك الأردن حجم التحويلات",
                      "شركات الصرافة أسعار الحوالات لبنان", "تطبيقات الحوالات إلى سورية",
                      "آمار تراکنش شاپرک", "مبلغ تراکنش کارتی ماهانه",
                      "JoPACC CliQ volumes", "Shaparak monthly report",
                      "remittance prices Gulf to Jordan"),
    "media": ("سعر صرف الدينار العراقي اليوم شفق", "اتفاق بغداد أربيل بشأن النفط",
              "قرار مصرف لبنان الجديد", "أزمة الكهرباء في الأردن والغاز المصري",
              "قیمت دلار در بازار آزاد دنیای اقتصاد", "ناترازی گاز زمستان",
              "هەواڵی نەوت و بودجە", "L'Orient-Le Jour taux parallèle",
              "Rudaw KRG oil export halt"),
    "archive": ("الوقائع العراقية أعداد سابقة", "الجريدة الرسمية الأردنية أرشيف",
                "الجريدة الرسمية اللبنانية مرسوم سعر الصرف", "قرارات مجلس الوزراء أرشيف",
                "آرشیو روزنامه رسمی قانون بودجه", "نرخ ارز سال‌های گذشته",
                "wayback machine CBI auction", "OPEC MOMR back issues archive",
                "ICC Iraq Turkey pipeline award text"),
    "physical_economy": ("ميناء أم قصر حركة الشحن", "ميناء الفاو الكبير وطريق التنمية",
                         "ميناء العقبة حركة البضائع", "خط الغاز العربي ضخ الغاز المصري",
                         "تقدير محصول القمح في سورية", "إهراءات القمح في مرفأ بيروت",
                         "پارس جنوبی تولید گاز", "صادرات نفت از جزیره خارگ",
                         "Ceyhan loadings Kirkuk pipeline", "FAO GIEWS Syria wheat"),
    "source_graph": ("وفقا لمصادر مطلعة على المفاوضات", "نقلا عن بيان وزارة الخزانة الأمريكية",
                     "حسب إحصاءات الجمارك التركية", "التبادل التجاري بين تركيا وسورية",
                     "به نقل از منابع آگاه", "بر اساس آمار گمرک چین",
                     "China customs crude imports by origin", "OFAC designation press release",
                     "Federal Register Iran general license"),
}
# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "SOMO monthly Official Selling Prices for Basrah Medium and Basrah Heavy",
     "source": "State Organization for Marketing of Oil (SOMO), Iraq",
     "coverage": "2017 onward for the two current grades; the older Basrah Light series runs "
                 "from the 1990s and is not continuous with them",
     "frequency": "monthly", "publication_lag_days": 0.0,
     "revisions": "never revised; a differential once announced stands for that month's liftings",
     "licence": "free, public", "history_from": "2017-06", "pit_feasible": True,
     "assets": ("XBRUSD", "XTIUSD", "USDINR"),
     "mechanism_families": ("administered_price", "release_surprise", "calendar_settlement"),
     "how_to_fetch": "somooil.gov.iq publishes the monthly OSP circular as a table of "
                     "differentials to the Oman/Dubai average (Asia), to Dated Brent (Europe) "
                     "and to the Argus Sour Crude Index (US); scrape the announcement page "
                     "monthly and key by (grade, destination region, delivery month)"},
    {"name": "Iraqi Ministry of Oil monthly export volume and revenue",
     "source": "Iraqi Ministry of Oil / SOMO",
     "coverage": "federal exports through Basrah and, separately, the northern route when it flows",
     "frequency": "monthly", "publication_lag_days": 3.0,
     "revisions": "occasionally restated in the annual report; the monthly print is the vintage",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": True,
     "assets": ("XBRUSD", "XTIUSD", "US500"),
     "mechanism_families": ("release_surprise", "quota_compliance", "physical_flow"),
     "how_to_fetch": "oil.gov.iq press release within the first days of each month; parse "
                     "barrels exported and USD revenue, and DERIVE the realised average price by "
                     "dividing -- the pairing is the part almost no other producer publishes"},
    {"name": "OPEC MOMR crude production: direct communication AND secondary sources",
     "source": "OPEC Secretariat Monthly Oil Market Report",
     "coverage": "every member and DoC participant; Iraq in both tables, Iran in both tables",
     "frequency": "monthly", "publication_lag_days": 12.0,
     "revisions": "prior months are revised in each issue, which is why a vintage read matters",
     "licence": "free, public", "history_from": "2003-01", "pit_feasible": True,
     "assets": ("XBRUSD", "XTIUSD", "USDINR"),
     "mechanism_families": ("release_surprise", "series_divergence", "quota_compliance"),
     "how_to_fetch": "download the MOMR PDF from opec.org each month and extract BOTH production "
                     "tables; store them as two series with the same cover date so the GAP is a "
                     "first-class observable rather than a reconciliation problem"},
    {"name": "Central Bank of Iraq daily dollar auction and platform allocation",
     "source": "Central Bank of Iraq", "coverage": "every business day, Sunday to Thursday",
     "frequency": "daily", "publication_lag_days": 0.0,
     "revisions": "never revised", "licence": "free, public", "history_from": "2012-01",
     "pit_feasible": False,
     "assets": ("XAUUSD", "USDTRY", "GBPTRY"),
     "mechanism_families": ("central_bank_surprise", "funding_stress", "administered_price"),
     "how_to_fetch": "cbi.iq publishes the auction result table daily; the page OVERWRITES, so "
                     "capture it each day and reconcile the history against the Wayback Machine "
                     "-- pit_feasible is FALSE by construction and the archive layer is the fix"},
    {"name": "Iraqi parallel-market dinar rate (Baghdad and Erbil)",
     "source": "the licensed exchange companies, reported daily by Shafaq News and Rudaw",
     "coverage": "Baghdad and Erbil quoted separately; the two differ and the spread is itself "
                 "a read on the internal dispute",
     "frequency": "daily", "publication_lag_days": 0.0,
     "revisions": "n/a", "licence": "free, public", "history_from": "2020-01",
     "pit_feasible": False,
     "assets": ("XAUUSD", "USDTRY", "XBRUSD"),
     "mechanism_families": ("parallel_premium", "funding_stress", "administered_price"),
     "how_to_fetch": "shafaq.com and rudaw.net publish a morning rate story most business days; "
                     "parse the Baghdad and Erbil quotes and compute the premium over the CBI's "
                     "official 1,320 with `parallel_premium`"},
    {"name": "US OFAC designations, general licences and Federal Register notices",
     "source": "US Department of the Treasury and the Federal Register",
     "coverage": "the whole sanctions record for Iran and Syria and the Iraqi banking actions",
     "frequency": "irregular", "publication_lag_days": 0.0,
     "revisions": "never revised; a delisting is a new dated act, not a correction",
     "licence": "free, public (US government work)", "history_from": "2010-01",
     "pit_feasible": True,
     "assets": ("XBRUSD", "XTIUSD", "USDCNH"),
     "mechanism_families": ("policy_event", "release_surprise", "failure"),
     "how_to_fetch": "the Federal Register API (federalregister.gov/api/v1/documents.json) "
                     "filtered on the Treasury/OFAC agency plus the SDN list change files; key "
                     "by publication date and by programme tag (IRAN, SYRIA, IRAQ)"},
    {"name": "Bank Markazi official, NIMA and reported free-market rial rates",
     "source": "Central Bank of Iran and the Persian financial press",
     "coverage": "the official table from the bank; the free rate from the market quote pages",
     "frequency": "daily", "publication_lag_days": 0.0,
     "revisions": "n/a", "licence": "free, public", "history_from": "2018-04",
     "pit_feasible": False,
     "assets": ("XAUUSD", "XAGUSD", "USDTRY"),
     "mechanism_families": ("parallel_premium", "central_bank_surprise", "inflation_expectation"),
     "how_to_fetch": "cbi.ir for the official and NIMA tables; tgju.org and donya-e-eqtesad.com "
                     "for the free-market quote. THREE SERIES, not one, and every downstream "
                     "cell must record which it used"},
    {"name": "Bahar Azadi gold-coin price and its premium over metal content",
     "source": "the Tehran coin market, quoted daily by the domestic press and quote pages",
     "coverage": "the full-size coin and the quarter coin, quoted separately",
     "frequency": "daily", "publication_lag_days": 0.0,
     "revisions": "n/a", "licence": "free, public", "history_from": "2017-01",
     "pit_feasible": False,
     "assets": ("XAUUSD", "XAGUSD"),
     "mechanism_families": ("inflation_expectation", "retail_flow", "seasonality"),
     "how_to_fetch": "tgju.org publishes the coin price and the computed premium (حباب) daily; "
                     "capture both alongside the free-market rial and pass them to "
                     "`coin_premium` with the 7.3224 g / 900 purity basis"},
    {"name": "Central Bank of Jordan policy rate, reserves and monetary aggregates",
     "source": "Central Bank of Jordan", "coverage": "1995 onward, uninterrupted",
     "frequency": "monthly, with same-day policy announcements", "publication_lag_days": 20.0,
     "revisions": "minor and documented", "licence": "free, public", "history_from": "1995-01",
     "pit_feasible": True,
     "assets": ("EURUSD", "XAUUSD", "USDILS"),
     "mechanism_families": ("central_bank_surprise", "carry_funding", "peg_control"),
     "how_to_fetch": "cbj.gov.jo statistical database; pull the policy rate, gross foreign "
                     "reserves and the reserve-months-of-imports line, and pair each policy date "
                     "with the FOMC date it follows to measure the under-matching"},
    {"name": "Banque du Liban weekly balance sheet: FX reserves, gold and currency in circulation",
     "source": "Banque du Liban", "coverage": "the whole collapse and the two decades before it",
     "frequency": "twice monthly", "publication_lag_days": 5.0,
     "revisions": "several lines were restated during the crisis; vintages differ materially",
     "licence": "free, public", "history_from": "2000-01", "pit_feasible": False,
     "assets": ("XAUUSD", "USDTRY", "EURTRY"),
     "mechanism_families": ("peg_stress", "failure", "funding_stress"),
     "how_to_fetch": "bdl.gov.lb publishes the bi-monthly balance sheet as PDF and XLS; parse "
                     "the FX reserve, gold and claims-on-the-public-sector lines and keep every "
                     "vintage -- a current-vintage series here is not point-in-time"},
    {"name": "The Lebanese parallel-rate series (banknote, Sayrafa and official)",
     "source": "the exchange-house market, the BdL Sayrafa print and the official rate circulars",
     "coverage": "2019-10 onward for the banknote rate; 2021-05 to 2023 for Sayrafa",
     "frequency": "daily", "publication_lag_days": 0.0,
     "revisions": "n/a", "licence": "free, public", "history_from": "2019-10",
     "pit_feasible": False,
     "assets": ("XAUUSD", "USDTRY", "EURILS"),
     "mechanism_families": ("parallel_premium", "failure", "peg_stress"),
     "how_to_fetch": "lirarate.org and the Lebanese press for the banknote rate; bdl.gov.lb for "
                     "Sayrafa and the official circulars. Store THREE columns and never one: "
                     "`lbp_official_rate` gives the administered leg for any date"},
    {"name": "Amman Stock Exchange daily foreign and Arab investor flow",
     "source": "Amman Stock Exchange", "coverage": "2005 onward",
     "frequency": "daily", "publication_lag_days": 0.0,
     "revisions": "the monthly bulletin restates the daily numbers; use the daily vintage",
     "licence": "free, public", "history_from": "2005-01", "pit_feasible": True,
     "assets": ("EURUSD", "XAUUSD", "US500"),
     "mechanism_families": ("institutional_flow", "positioning", "equity_mechanics"),
     "how_to_fetch": "ase.com.jo trading-statistics pages publish the daily buy/sell split by "
                     "nationality; pull net non-Jordanian flow and treat it as a GULF-MONEY "
                     "risk gauge rather than as a Jordanian equity signal"},
    {"name": "Arab Potash and JPMC production, export tonnage and realised price",
     "source": "the producers' own published annual and quarterly disclosures, plus Jordanian "
               "Department of Statistics export tables",
     "coverage": "2010 onward with a long earlier history in the DoS tables",
     "frequency": "quarterly and annual, with monthly export tonnage in the DoS trade series",
     "publication_lag_days": 45.0,
     "revisions": "annual figures supersede quarterly ones",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": True,
     "assets": ("CORN", "WHEAT", "SOYBEAN"),
     "mechanism_families": ("input_cost", "corporate_flow", "physical_flow"),
     "how_to_fetch": "dos.gov.jo foreign-trade tables for monthly potash and phosphate export "
                     "tonnage and value (so realised price is derivable), and the producers' own "
                     "published reports for capacity and contract commentary. The GRAIN leg is "
                     "the executable end; the producer is an ACTOR and never an instrument"},
    {"name": "UN Comtrade and partner customs MIRROR trade for Syria, Iran and Iraq",
     "source": "UN Comtrade; China GACC; India DGCI&S; Turkey TUIK",
     "coverage": "all partners that report; Syria and Iran appear as partner rows even when they "
                 "do not report themselves",
     "frequency": "monthly to annual depending on the reporter", "publication_lag_days": 60.0,
     "revisions": "reporters revise; Comtrade carries the vintage",
     "licence": "free, public / open data", "history_from": "2000-01", "pit_feasible": True,
     "assets": ("WHEAT", "COTTON", "USDCNH"),
     "mechanism_families": ("mirror_statistics", "physical_flow", "transfer"),
     "how_to_fetch": "comtradeplus.un.org API by reporter and partner, plus the three national "
                     "portals for the timelier monthly prints; the Chinese crude line by origin "
                     "is the standing example of what a mirror reveals that a self-report "
                     "does not"},
    {"name": "FAO/GIEWS country briefs and WFP priced food baskets (SY, LB, JO)",
     "source": "FAO Global Information and Early Warning System; WFP VAM",
     "coverage": "Syria at governorate level, Lebanon and Jordan nationally",
     "frequency": "monthly to quarterly", "publication_lag_days": 30.0,
     "revisions": "crop estimates are revised through the season",
     "licence": "free, public", "history_from": "2012-01", "pit_feasible": True,
     "assets": ("WHEAT", "CORN", "SUGAR"),
     "mechanism_families": ("physical_flow", "import_demand", "release_surprise"),
     "how_to_fetch": "fao.org/giews country briefs for production and import requirements; "
                     "dataviz.vam.wfp.org for the priced basket by governorate. THIS IS THE "
                     "NAMED SUBSTITUTE for the absent Syrian statistics and it is cited as such"},
    {"name": "UNHCR and OCHA refugee response plans, funding appeals and population figures",
     "source": "UNHCR Operational Data Portal; OCHA Financial Tracking Service",
     "coverage": "Syria regional response (JO, LB, TR, IQ) and Iraqi internal displacement",
     "frequency": "monthly population figures; annual appeals with dated launches",
     "publication_lag_days": 15.0,
     "revisions": "population figures are revised as registration changes",
     "licence": "free, public / open data", "history_from": "2012-01", "pit_feasible": True,
     "assets": ("WHEAT", "SUGAR", "USDTRY"),
     "mechanism_families": ("fiscal_shock", "policy_event", "import_demand"),
     "how_to_fetch": "data.unhcr.org for registered population by country and month; "
                     "fts.unocha.org "
                     "for the funding actually received against each appeal. A REFUGEE-DRIVEN "
                     "FISCAL SHOCK IS A DATED PUBLISHED EVENT and this is where the dates are"},
    {"name": "EIA Strait of Hormuz transit volumes and world chokepoint analysis",
     "source": "US Energy Information Administration",
     "coverage": "annual and periodic estimates of crude, condensate and LNG transiting Hormuz",
     "frequency": "annual with periodic updates", "publication_lag_days": 120.0,
     "revisions": "estimates are revised with better tracking data",
     "licence": "free, public (US government work)", "history_from": "2011-01",
     "pit_feasible": True,
     "assets": ("XBRUSD", "XNGUSD", "USDJPY"),
     "mechanism_families": ("chokepoint_risk", "physical_flow", "failure"),
     "how_to_fetch": "eia.gov/international/analysis chokepoint pages; pull the transit volume "
                     "and the destination split. THE BYPASS GEOGRAPHY BELONGS TO `gulf` -- this "
                     "pack carries the RISK side and uses Duqm and Ras Markaz as its control"},
    {"name": "Arab Gas Pipeline flows, Jordanian electricity imports and Lebanese power supply",
     "source": "Jordanian Ministry of Energy and NEPCO annual reports; Lebanese EDL and the "
               "published Egypt-Jordan-Syria-Lebanon arrangements",
     "coverage": "2003 onward for the pipeline; the Lebanese leg only when it has operated",
     "frequency": "monthly to annual", "publication_lag_days": 60.0,
     "revisions": "annual reports supersede monthly statements",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": True,
     "assets": ("XNGUSD", "GER40", "USDILS"),
     "mechanism_families": ("physical_flow", "policy_event", "input_cost"),
     "how_to_fetch": "memr.gov.jo and NEPCO's annual report for gas received and electricity "
                     "generated by fuel; the Egyptian and Israeli export announcements date the "
                     "supply changes. The pipeline's Lebanese and Syrian legs are intermittent "
                     "and the intermittency is the observable"},
    {"name": "Iranian natural gas production, South Pars output and winter power curtailment",
     "source": "SHANA (the oil ministry news agency), the Ministry of Energy and the annual "
               "energy balance",
     "coverage": "annual production with periodic monthly commentary; curtailment is reported "
                 "episodically through the winter",
     "frequency": "annual with episodic monthly reporting", "publication_lag_days": 90.0,
     "revisions": "annual balances are restated",
     "licence": "free, public", "history_from": "2015-01", "pit_feasible": False,
     "assets": ("XNGUSD", "XBRUSD", "XTIUSD"),
     "mechanism_families": ("supply_schedule", "seasonality", "failure"),
     "how_to_fetch": "shana.ir for production and curtailment reporting in Persian; the winter "
                     "industrial curtailment announcements are dated and are the measurable "
                     "event. pit_feasible is FALSE because the annual balance is restated and "
                     "the monthly commentary is not a series"},
    {"name": "Iraqi Development Road and Grand Faw port programme milestones",
     "source": "the Iraqi General Company for Ports, the Ministry of Transport and the published "
               "intergovernmental agreements with Turkey, Qatar and the UAE",
     "coverage": "2023 onward as a named programme; the Faw port contract history runs from 2010",
     "frequency": "irregular, milestone-driven", "publication_lag_days": 0.0,
     "revisions": "dates slip and the slip is itself the event",
     "licence": "free, public", "history_from": "2023-04", "pit_feasible": True,
     "assets": ("XBRUSD", "USDTRY", "US500"),
     "mechanism_families": ("supply_schedule", "policy_event", "physical_flow"),
     "how_to_fetch": "scp.gov.iq and the Ministry of Transport announcements, cross-read against "
                     "the Turkish side's statements; record each milestone with its announced "
                     "date and its realised date, because the GAP between them is the object"},
    {"name": "Jordanian Department of Statistics CPI, trade and tourism series",
     "source": "Department of Statistics, Jordan", "coverage": "complete and uninterrupted",
     "frequency": "monthly", "publication_lag_days": 21.0,
     "revisions": "documented and small", "licence": "free, public", "history_from": "2000-01",
     "pit_feasible": True,
     "assets": ("EURUSD", "XAUUSD", "CORN"),
     "mechanism_families": ("release_surprise", "peg_control", "import_demand"),
     "how_to_fetch": "dos.gov.jo statistical database; the monthly CPI, the trade tables and the "
                     "tourism receipts. THIS IS THE CONTROL SERIES OF THE PACK: the only "
                     "complete monthly macro record among the five, which is what lets a "
                     "regional shock be separated from a country-specific one"},
)
# --------------------------------------------------------------------------- actors
#: TWENTY-TWO ACTORS: five Iraqi, five Iranian, three each for Jordan, Lebanon and Syria, and
#: three shared. `jurisdiction` is this pack's own field and is folded into the framework row's
#: notes rather than dropped, because an actor attributed to "the Levant" reads as a region and
#: the whole point of this pack is that a peg that held and a peg that failed are not one place.
ACTORS: tuple[dict[str, Any], ...] = (
    # ------------------------------------------------------------------ Iraq
    {"name": "SOMO as the setter of the Basrah Official Selling Prices",
     "jurisdiction": "iq",
     "holds": "the sole marketing right for Iraqi federal crude, the term contract book with the "
              "Asian, European and American refiners, and the monthly differential for Basrah "
              "Medium and Basrah Heavy",
     "forced_to": ("announce a differential EVERY MONTH for the following month's liftings, "
                   "because the term contracts are struck against it",
                   "price against the Oman/Dubai average for Asia and against other markers "
                   "elsewhere, so the grade's economics are anchored to benchmarks it does not set",
                   "keep the barrels moving: Iraq's budget is a salary bill and an export "
                   "shortfall is a fiscal event within weeks"),
     "when": "in the first week of the month, AFTER Saudi Aramco's OSP sets the regional "
             "reference; the announcement lands in Baghdad business hours (about 07:00-13:00 UTC)",
     "information": ("the term nomination book before anyone outside sees it",
                     "the loading programme at Basrah and the berth schedule",
                     "the discounts its Asian competitors are actually offering",
                     "the federal export volume before the ministry publishes it"),
     "constraints": ("the Saudi OSP, which is announced first and anchors the region",
                     "an OPEC+ quota and a published compensation schedule",
                     "a single loading complex in the far south, inside the Strait of Hormuz",
                     "a fiscal breakeven that makes volume politically compulsory"),
     "instruments": ("XBRUSD", "XTIUSD", "USDINR"),
     "counterparties": ("the Indian and Chinese refiners who take the largest share",
                        "the European and Mediterranean refiners on the lighter grades",
                        "Saudi Aramco and ADNOC as the competing sellers into Asia",
                        "the Iraqi Ministry of Finance, whose budget is the revenue"),
     "observables": ("the monthly differential for each grade and destination region",
                     "the ministry's monthly export volume and revenue, which give realised price",
                     "the ORDER and GAP between the Saudi announcement and the Iraqi one",
                     "the term versus spot share in each month's liftings"),
     "impact": "an administered differential on roughly 3.5 mb/d of seaborne crude is a real "
               "price signal for the Asian sour complex, and because it is ANNOUNCED rather than "
               "traded it can be studied as an event rather than inferred from a spread",
     "persistence": "one month per announcement; the level persists across months and the "
                    "CHANGE is the event",
     "falsifier": "Basrah OSP change months show no measurable move in the Brent-WTI or the "
                  "Asian refining-margin complex once the Saudi OSP announced days earlier is "
                  "controlled for; if the Saudi number explains all of it, the Iraqi "
                  "announcement is a follower and not an information event",
     "notes": "SOMO IS AN ACTOR AND NEVER AN INSTRUMENT; the two-lane order forbids hunting a "
              "name and no Iraqi entity is listed anywhere in any case"},
    {"name": "The Kurdistan Regional Government's Ministry of Natural Resources",
     "jurisdiction": "iq",
     "holds": "the fields of the Kurdistan Region, the production-sharing contracts with the "
              "international operators, and a pipeline to Ceyhan that has been SHUT since "
              "2023-03-25",
     "forced_to": ("publish its OWN oil and budget position, in Kurdish and English, because its "
                   "legitimacy with its own public and its contractors depends on it -- and "
                   "those figures DIFFER FROM BAGHDAD'S, which is the observable",
                   "pay international operators whose contracts predate the federal budget law",
                   "negotiate in public, because every step of the Baghdad-Erbil dispute is "
                   "litigated and reported"),
     "when": "budget and export statements are irregular and are usually issued around federal "
             "budget votes and around each round of restart negotiations",
     "information": ("actual field production and the operators' cost-recovery positions",
                     "the real state of the restart negotiations with Baghdad and Ankara",
                     "the trucked-export volumes that continued while the pipeline was shut"),
     "constraints": ("an ICC award that made the Turkish side liable for accepting the crude",
                     "a federal supreme court ruling against the region's independent contracts",
                     "no route to water except through Turkey",
                     "a salary bill of its own that the shutdown made unpayable on time"),
     "instruments": ("XBRUSD", "XTIUSD", "USDTRY"),
     "counterparties": ("the federal government in Baghdad and SOMO",
                        "Turkey as the transit state and the award's respondent",
                        "the international operators holding the production-sharing contracts",
                        "the traders who lifted the crude at Ceyhan before the halt"),
     "observables": ("the KRG's own published export and revenue statements",
                     "the GAP between Erbil's figures and Baghdad's for the same barrels",
                     "Ceyhan loadings, or their absence, from the Turkish side",
                     "each dated restart announcement and the volume that actually follows"),
     "impact": "roughly 450 kb/d of seaborne light crude left the market on a dated legal ruling "
               "and stayed out for more than two years -- one of the largest single non-OPEC "
               "supply removals of the period, and one with a court date rather than a war on it",
     "persistence": "years: the shutdown has outlasted every announced restart deadline",
     "falsifier": "the 2023-03-25 halt shows no measurable effect on Brent-Dubai or on "
                  "Mediterranean light-sour differentials once Iraqi FEDERAL exports over the "
                  "same window are controlled for; if Basrah made up the volume, this was a "
                  "routing event and not a supply event",
     "notes": "THE KRG PUBLISHES IN KURDISH and its numbers are not translations of Baghdad's; "
              "a crawler that reads only Arabic misses one side of the only public dispute that "
              "moves this much crude"},
    {"name": "The Central Bank of Iraq as the state's dollar window",
     "jurisdiction": "iq",
     "holds": "the daily dollar auction, the transfer-compliance platform, the official rate the "
              "cabinet sets, and the foreign reserves the oil revenue accumulates",
     "forced_to": ("convert oil dollars into dinars every business day, because several million "
                   "public salaries are paid in dinars and the revenue arrives in dollars",
                   "screen every outward transfer through the compliance platform, because "
                   "correspondent access depends on it",
                   "defend an administered rate it does not set"),
     "when": "the auction result is published each business day around 08:00 UTC; the "
             "compliance rules change when Washington changes them",
     "information": ("which banks are being refused and why",
                     "the true composition of demand between trade and flight",
                     "the reserve position before it is published"),
     "constraints": ("US Treasury supervision of the dollar channel, which is a foreign "
                     "administrative constraint on a domestic monetary institution",
                     "a cabinet that owns the rate",
                     "a parallel market it cannot close and does not control"),
     "instruments": ("XAUUSD", "USDTRY", "GBPTRY"),
     "counterparties": ("the Iraqi commercial banks and the exchange companies",
                        "the US Federal Reserve Bank of New York and the US Treasury",
                        "the Ministry of Finance, whose salary bill is the demand",
                        "the importers, principally of Turkish and Iranian goods"),
     "observables": ("the daily allocated volume and the cash-versus-transfer split",
                     "the compliance rejection share",
                     "the parallel premium, which is the same-day verdict on both",
                     "the dated US Treasury actions that move the plumbing"),
     "impact": "when the premium widens, Iraqi import costs and domestic gold demand rise "
               "together; the gold leg is the one this desk can trade and the mechanism is a "
               "household fleeing an administered rate it cannot access",
     "persistence": "weeks: a compliance action's effect on the premium decays as banks adapt, "
                    "which is exactly why the event window must be short and pre-registered",
     "falsifier": "dated US Treasury actions on Iraqi banks show no measurable widening of the "
                  "parallel premium in the following ten sessions once oil revenue and the "
                  "auction volume are controlled for",
     "notes": "the plumbing is FISCAL with a monetary label; treating the CBI as an inflation "
              "targeter is the standard error a G10-trained model makes here"},
    {"name": "The Iraqi Ministry of Finance as a salary-bill-constrained forced seller of oil",
     "jurisdiction": "iq",
     "holds": "a budget in which public salaries, pensions and the social safety net dominate, "
              "financed almost entirely by oil revenue",
     "forced_to": ("sell crude at whatever the market pays, every month, because the payroll "
                   "does not wait for a better price",
                   "fund a salary bill that grew through every high-price period and cannot "
                   "easily shrink in a low-price one",
                   "borrow domestically from state banks when revenue falls short"),
     "when": "monthly, on the payroll cycle; the annual budget law is a dated parliamentary event",
     "information": ("the true payroll and pension headcount",
                     "the arrears position with contractors and with the KRG",
                     "the month's oil revenue before it is published"),
     "constraints": ("a fiscal breakeven well above most producers'",
                     "an OPEC+ quota that caps the volume side of the revenue",
                     "a political economy in which the salary bill is the social contract"),
     "instruments": ("XBRUSD", "XTIUSD", "US500"),
     "counterparties": ("SOMO as the seller", "the state banks as the domestic lender",
                        "the KRG, in a revenue-sharing dispute that is also a budget line",
                        "the CBI, whose auction converts the revenue"),
     "observables": ("the annual budget law's assumed oil price and export volume",
                     "the monthly revenue print against it",
                     "the arrears and the domestic borrowing lines",
                     "the compensation schedule, which promises to sell LESS"),
     "impact": "a producer whose payroll forces volume is a producer whose quota compliance is "
               "structurally weak -- which is precisely why Iraq keeps filing compensation "
               "schedules and why the promise and the outcome are worth measuring separately",
     "persistence": "quarters: a fiscal squeeze persists until the price recovers or the budget "
                    "is restructured, and it has never been restructured",
     "falsifier": "months in which the published budget assumptions were missed show no "
                  "measurable change in Iraqi export volume relative to quota once seasonal "
                  "domestic crude burn is controlled for",
     "notes": "the mechanism is FORCED SELLING, which is the rarest and most useful actor shape "
              "this desk collects, and here it is written into a budget law every year"},
    {"name": "The Iraqi household and merchant as a dollar-and-gold saver",
     "jurisdiction": "iq",
     "holds": "dinar income, dollar-denominated import costs, and a strong preference for "
              "physical dollars and gold as the store of value",
     "forced_to": ("buy dollars in the parallel market when the official channel is rationed",
                   "buy gold when the premium signals that the administered rate is not "
                   "available at scale",
                   "import through Turkish and Iranian suppliers, which prices the lira and the "
                   "rial into the domestic basket"),
     "when": "continuously, with a month-end concentration on the salary cycle",
     "information": ("which exchange shops are clearing and at what rate",
                     "whether a transfer will be approved this week",
                     "the local gold souk's premium over the international price"),
     "constraints": ("no access to the official rate without documentation",
                     "a cash economy with limited banking penetration",
                     "a cross-border price that moves with the lira and the rial"),
     "instruments": ("XAUUSD", "XAGUSD", "USDTRY"),
     "counterparties": ("the exchange companies", "the gold souk",
                        "Turkish and Iranian exporters", "the banks, for those who can use them"),
     "observables": ("the parallel premium", "the local gold premium over the world price",
                     "the cash share of the CBI auction", "Turkish export statistics to Iraq"),
     "impact": "Iraq is a large physical gold market by regional standards and the demand is "
               "counter-cyclical to confidence in the dinar; that is a real, if modest, "
               "component of regional physical demand and it is the household end of OPECN-D",
     "persistence": "weeks to months, and it ratchets: confidence lost returns slowly",
     "falsifier": "widening-premium months show no measurable rise in regional physical gold "
                  "demand indicators or in the local gold premium once the world gold price and "
                  "the Hijri festival season are controlled for",
     "notes": "the retail-ecology layer is where this actor is actually visible, which is why a "
              "pack with no retail layer cannot see it at all"},
    # ------------------------------------------------------------------ Iran
    {"name": "NIOC and the Ministry of Petroleum as a sanctioned exporter",
     "jurisdiction": "ir",
     "holds": "a top-five oil reserve base, the world's second-largest gas reserves, the South "
              "Pars complex, and an export capability whose USE is set in Washington rather "
              "than in Tehran",
     "forced_to": ("sell at a discount to buyers willing to take the sanctions risk, because the "
                   "alternative is not selling",
                   "route through intermediaries and re-labelling, which is why the mirror "
                   "customs of the buyer is the only public quantity",
                   "keep producing: shutting a mature field in has recovery costs"),
     "when": "production and export respond within weeks to months of a published US act; the "
             "acts themselves land in US hours",
     "information": ("its own real production and storage position",
                     "the actual discount being realised",
                     "the state of the floating-storage inventory"),
     "constraints": ("the published sanctions regime and its enforcement intensity",
                     "a small number of willing buyers, which concentrates price power on the "
                     "buy side",
                     "domestic refinery and gas-injection demand that competes for the barrel"),
     "instruments": ("XBRUSD", "XTIUSD", "USDCNH"),
     "counterparties": ("Chinese independent refiners as the residual buyer",
                        "the shipping and insurance intermediaries",
                        "OPEC, which prints two different numbers for its output",
                        "the US Treasury, which is the actual constraint"),
     "observables": ("the two OPEC series and the gap between them",
                     "Chinese customs crude imports by declared origin",
                     "the dated OFAC and Federal Register acts",
                     "floating storage as reported by public tracking"),
     "impact": "a swing of one to two million barrels a day driven by administrative decisions "
               "rather than by price is a supply function with a POLICY argument, and it is the "
               "single largest discretionary supply variable outside OPEC+ itself",
     "persistence": "quarters to years: a sanctions regime persists until the next dated act",
     "falsifier": "the dated US acts show no measurable effect on Brent term structure or on the "
                  "Brent-Dubai relationship in the following quarter once OPEC+ decisions in the "
                  "same window are controlled for",
     "notes": "NOTHING HERE TOUCHES A SANCTIONED SYSTEM. Every observable named is a published "
              "OPEC table, a published US government notice or a partner country's own customs "
              "return; see ACCESS_CONSTRAINTS"},
    {"name": "Bank Markazi as the administrator of a lattice of exchange rates",
     "jurisdiction": "ir",
     "holds": "the 42,000 preferential rate, the NIMA/ETS integrated-market rates, the reserve "
              "position that sanctions have made partly unusable, and no control at all over "
              "the free market",
     "forced_to": ("allocate scarce hard currency by administrative rule, which creates the "
                   "eligibility rents that make the lattice persist",
                   "let exporters surrender at a rate below the free market, which is a tax",
                   "watch the free rate it does not set become the country's real price signal"),
     "when": "rate tables are published daily; allocation rule changes are decreed irregularly "
             "and are dated events",
     "information": ("the true accessible reserve position",
                     "which importers are receiving allocation",
                     "the surrender compliance of exporters"),
     "constraints": ("reserves that are partly frozen abroad",
                     "an inflation rate that makes any fixed rate a subsidy within months",
                     "a political commitment to cheap essential imports"),
     "instruments": ("XAUUSD", "XAGUSD", "USDTRY"),
     "counterparties": ("the importers who receive allocation",
                        "the exporters who must surrender",
                        "the free market and the coin market, which arbitrage the gap",
                        "the households who hold the result"),
     "observables": ("the three published rate levels and the spreads between them",
                     "dated allocation-rule decrees",
                     "the coin premium, which prices the expectation",
                     "the Shaparak card-transaction value as a nominal spending proxy"),
     "impact": "the gap between the administered and free rates IS the domestic inflation "
               "process; the coin premium is where households express it, and physical gold "
               "demand is the executable end",
     "persistence": "months: a decree resets the level and the gap re-opens with inflation",
     "falsifier": "widening official-to-free gaps show no measurable effect on the coin premium "
                  "or on regional physical gold demand once the world gold price and the Nowruz "
                  "season are controlled for",
     "notes": "THREE PRICES AT ONE MOMENT is the fact that breaks naive Iranian FX research; "
              "`parallel_premium` refuses to answer unless it is told which pair it was given"},
    {"name": "The Iranian household as a gold-coin and hard-currency saver",
     "jurisdiction": "ir",
     "holds": "rial income in a high-inflation economy, no access to any international financial "
              "product, and a deep, liquid, legal domestic market in gold coins and bullion",
     "forced_to": ("store value in something that is not the rial, because a rial deposit loses "
                   "to inflation almost every year",
                   "choose between coins, bullion, dollars, equities and property, and rotate "
                   "between them as expectations shift",
                   "pay a PREMIUM for the coin over its own metal content, which is the price of "
                   "that optionality"),
     "when": "continuously, with a pronounced pre-Nowruz concentration and a second one around "
             "the budget's FX assumptions each spring",
     "information": ("the street's view of the free rate before the quote pages print it",
                     "which coin sizes are actually available",
                     "the local physical premium over the world price"),
     "constraints": ("no access to an international broker or a foreign bank account",
                     "capital controls on physical export",
                     "a domestic equity market quoted in a depreciating unit"),
     "instruments": ("XAUUSD", "XAGUSD", "USDTRY"),
     "counterparties": ("the Tehran coin and bullion market",
                        "the Tehran Stock Exchange, as the rotation's other leg",
                        "the free-market dollar dealers"),
     "observables": ("the Bahar Azadi price and its published premium (حباب)",
                     "the free-market rial", "TSE retail net flow",
                     "Shaparak transaction value as a nominal spending proxy"),
     "impact": "Iran is one of the larger physical gold demand centres in the region and the "
               "demand is driven by a domestic expectations variable that is PUBLISHED DAILY; "
               "that is a genuine, legible XAUUSD demand-side observable rather than colour",
     "persistence": "weeks: the premium mean-reverts as the free rate stabilises, and it "
                    "ratchets during a sanctions escalation",
     "falsifier": "coin-premium spikes show no measurable relationship to regional physical gold "
                  "demand or to XAUUSD once the world price, the dollar index and the Hijri and "
                  "Nowruz seasons are controlled for",
     "notes": "the whole mechanism lives in the retail-ecology and media layers and is invisible "
              "to an official-sources-only crawl of Iran"},
    {"name": "The Iranian power and gas balancer in winter",
     "jurisdiction": "ir",
     "holds": "the world's second-largest gas reserves and a domestic consumption profile that "
              "exceeds deliverable supply in cold weather",
     "forced_to": ("curtail industry and power generation when household heating demand peaks, "
                   "because households are not curtailable",
                   "burn mazut and liquid fuels in power stations when gas is short, which "
                   "substitutes into the oil balance",
                   "reduce gas injection into oil fields, which costs oil production later"),
     "when": "each winter, with the dated curtailment announcements concentrated from December "
             "to February",
     "information": ("the real deliverability of South Pars in cold weather",
                     "the storage and linepack position",
                     "which industries will be cut first"),
     "constraints": ("subsidised domestic prices that guarantee demand growth",
                     "sanctions that slow the investment needed to raise deliverability",
                     "a pressure decline at South Pars that is publicly acknowledged"),
     "instruments": ("XNGUSD", "XBRUSD", "XTIUSD"),
     "counterparties": ("Iraqi buyers of Iranian gas and power, which is how this becomes an "
                        "Iraqi electricity story every summer",
                        "Turkish gas imports under the long-term contract",
                        "domestic industry, principally steel, cement and petrochemicals"),
     "observables": ("dated curtailment announcements in the Persian press",
                     "liquid-fuel burn in the power sector",
                     "Iraqi electricity shortfalls attributed to Iranian supply",
                     "Turkish import interruptions"),
     "impact": "a large gas-reserve holder that is short gas in winter is an OIL consumer in "
               "winter; the substitution is real and it is announced, which makes it an event "
               "rather than a seasonal dummy",
     "persistence": "one season, recurring annually and worsening on a published trend",
     "falsifier": "dated Iranian curtailment announcements show no measurable effect on regional "
                  "liquid-fuel demand indicators or on the crude complex once northern-hemisphere "
                  "heating-degree days are controlled for",
     "notes": "this is the mechanism that connects an Iranian domestic constraint to an Iraqi "
              "summer electricity crisis and to the crude balance, and all three legs are public"},
    {"name": "The Majlis and the budget's assumed oil price and exchange rate",
     "jurisdiction": "ir",
     "holds": "the annual budget law, which fixes the assumed export volume, the assumed price "
              "and the exchange rate at which oil revenue is converted",
     "forced_to": ("pass a budget before the Solar Hijri year begins at Nowruz, which is a "
                   "DERIVED calendar date and not 1 January",
                   "state an exchange-rate assumption in public, which the free market then "
                   "immediately prices against",
                   "reconcile a subsidy commitment with a revenue forecast that sanctions make "
                   "unknowable"),
     "when": "the budget bill is presented in late autumn and passed before Nowruz; the fiscal "
             "year begins on the derived Nowruz date",
     "information": ("the government's own revenue expectation",
                     "the intended allocation rate for essential imports",
                     "the planned subsidy envelope"),
     "constraints": ("an export volume it does not control",
                     "an inflation rate that erodes any stated rate within the year",
                     "a political floor under subsidised goods"),
     "instruments": ("XBRUSD", "XAUUSD", "XNGUSD"),
     "counterparties": ("the government and Bank Markazi",
                        "the free market, which trades against the stated assumption",
                        "the households whose subsidies are the budget's largest line"),
     "observables": ("the published budget assumptions and the date of passage",
                     "the free rate's move around the presentation and the vote",
                     "the subsequent realised allocation rate"),
     "impact": "a state that publishes its own FX assumption hands the market a target; the "
               "spread between the assumption and the free rate on the day of passage is a "
               "measurable credibility gauge",
     "persistence": "one fiscal year, resetting on a derived date each spring",
     "falsifier": "budget-passage windows show no measurable move in the free-market rial or the "
                  "coin premium relative to matched non-budget weeks in the same quarter",
     "notes": "THE FISCAL YEAR IS SOLAR HIJRI and `iran_fiscal_year_start` derives it; a study "
              "that uses calendar quarters for Iran is using the wrong year"},
    # ------------------------------------------------------------------ Jordan
    {"name": "The Central Bank of Jordan as the defender of a peg that has never broken",
     "jurisdiction": "jo",
     "holds": "0.7090 dinars to the dollar since 1995, a reserve position measured in months of "
              "imports, and a policy rate that follows the Fed by construction",
     "forced_to": ("follow the Fed, because a hard peg has no independent rate -- but it has "
                   "repeatedly moved by LESS than the full step, which is the peg's only degree "
                   "of freedom and it is published",
                   "hold reserves against shocks it does not cause: two refugee waves, a "
                   "Syrian border closure, a Lebanese collapse and an Iraqi trade disruption",
                   "keep the IMF programme's targets, because the external financing depends "
                   "on them"),
     "when": "rate decisions follow the FOMC within hours; the monthly bulletin carries reserves",
     "information": ("the true composition of reserves including deposited support",
                     "the banking system's dollarisation ratio in real time",
                     "the pipeline of external grants and their timing"),
     "constraints": ("no independent monetary policy at all",
                     "an energy import bill that is a terms-of-trade shock generator",
                     "an economy whose neighbours generate fiscal shocks it must absorb"),
     "instruments": ("EURUSD", "XAUUSD", "USDILS"),
     "counterparties": ("the Federal Reserve, by construction",
                        "the IMF under the Extended Fund Facility",
                        "the Gulf states and the US as grant and deposit providers",
                        "the domestic banks, whose dollarisation is the peg's thermometer"),
     "observables": ("the CBJ-minus-Fed step at each decision",
                     "gross reserves and months of import cover",
                     "the deposit dollarisation ratio",
                     "the dated grant and deposit announcements"),
     "impact": "THE CONTROL. Jordan absorbs the same regional shocks as Lebanon and Syria and "
               "does not devalue; a shock that moves the Lebanese rate and not the Jordanian one "
               "is a Lebanese solvency fact, and a shock that moves both is regional",
     "persistence": "thirty years and counting; the persistence IS the finding",
     "falsifier": "regional shock windows show the Jordanian peg under measurable strain -- "
                  "reserve drawdown, dollarisation rise or a CBJ step that exceeds the Fed's -- "
                  "which would make Jordan a treated unit rather than a control and would "
                  "invalidate every paired test in this pack that uses it",
     "notes": "naming the control explicitly is what turns five neighbours into an "
              "identification strategy instead of five separate anecdotes"},
    {"name": "Arab Potash and the Jordan Phosphate Mines Company as world-scale fertiliser "
             "exporters",
     "jurisdiction": "jo",
     "holds": "a Dead Sea potash concession that is among the top ten producers worldwide, large "
              "phosphate rock reserves, and the Aqaba export terminal that ships both",
     "forced_to": ("sell into annual and semi-annual CONTRACT settlements with Indian and "
                   "Chinese buyers, which are announced prices rather than continuous ones",
                   "ship through one port on the Red Sea, whose access has been disrupted by "
                   "regional shipping risk",
                   "price against a world market dominated by Belarusian, Russian and Canadian "
                   "supply"),
     "when": "contract settlements are announced events; monthly export tonnage appears in the "
             "Jordanian trade statistics with about a six-week lag",
     "information": ("its own contracted tonnage and realised price before publication",
                     "the state of the Indian and Chinese negotiations",
                     "Aqaba's loading schedule"),
     "constraints": ("a single port and a single concession",
                     "energy costs, since phosphate processing is energy-intensive",
                     "a world price set by much larger producers"),
     "instruments": ("CORN", "WHEAT", "SOYBEAN"),
     "counterparties": ("Indian and Chinese fertiliser importers",
                        "the Jordanian treasury, for which these are major export earners",
                        "the global fertiliser trade, where the price is set"),
     "observables": ("contract settlement announcements and their level",
                     "monthly export tonnage and value from the Jordanian trade tables",
                     "Aqaba throughput", "world potash and phosphate price indices"),
     "impact": "fertiliser cost is a real input to planting economics; a route from a Jordanian "
               "mining fact into CORN and WHEAT is lawful and executable, whereas a route into "
               "the producer's own shares is forbidden by the two-lane order and is not taken",
     "persistence": "one contract period, six to twelve months",
     "falsifier": "potash and phosphate price and tonnage changes show no measurable effect on "
                  "the grain complex at any horizon once natural gas (the ammonia input) and the "
                  "Belarus and Russia supply share are controlled for -- in which case this is a "
                  "gas story wearing a Jordanian label",
     "notes": "THE CONTROL IS NAMED IN THE MECHANISM, not left to the reader: gas and the "
              "Belarus/Russia share are the two things that must be partialled out first"},
    {"name": "NEPCO and the Jordanian energy import bill",
     "jurisdiction": "jo",
     "holds": "a national electricity company that buys gas through the Arab Gas Pipeline and "
              "from Israeli fields, and a country with almost no hydrocarbon production of its own",
     "forced_to": ("import essentially all of its primary energy, which makes the terms of trade "
                   "a fiscal variable",
                   "switch fuels when the pipeline is interrupted, at a cost that lands on the "
                   "budget",
                   "hold long-term supply contracts whose politics are regional"),
     "when": "continuously, with the contract and supply changes as dated announcements",
     "information": ("the real delivered cost under each contract",
                     "the state of the pipeline and the interconnection",
                     "the arrears position with suppliers"),
     "constraints": ("no domestic resource base",
                     "a pipeline that crosses Syria and has been interrupted",
                     "a politically sensitive supply relationship"),
     "instruments": ("XNGUSD", "GER40", "USDILS"),
     "counterparties": ("Egyptian gas through the Arab Gas Pipeline",
                        "Israeli gas under the published supply agreement",
                        "the Jordanian treasury, which carries the subsidy",
                        "Lebanon and Syria as the pipeline's other legs"),
     "observables": ("gas received and electricity generated by fuel in the NEPCO annual report",
                     "dated supply interruptions and contract announcements",
                     "the Jordanian energy import bill in the trade statistics"),
     "impact": "an energy price shock is a Jordanian FISCAL shock rather than a monetary one, "
               "because the peg absorbs none of it; that is the clean mechanism by which a gas "
               "price reaches a pegged economy's budget instead of its currency",
     "persistence": "quarters: a supply interruption persists until the route is restored",
     "falsifier": "dated pipeline interruptions show no measurable effect on the Jordanian "
                  "energy import bill or on the regional gas complex once European gas prices "
                  "and Egyptian export policy are controlled for",
     "notes": "this is the Jordanian end of OPECN-P and it is the reason the Arab Gas Pipeline "
              "is a domain rather than a footnote"},
    # ------------------------------------------------------------------ Lebanon
    {"name": "Banque du Liban as a central bank that ran out of the ability to defend",
     "jurisdiction": "lb",
     "holds": "the wreckage of a twenty-two-year peg, the Sayrafa platform's legacy, a large "
              "gold holding that was never sold, and a balance sheet whose losses are the "
              "country's central political question",
     "forced_to": ("publish a balance sheet on a fixed cycle throughout the collapse, which is "
                   "why every stage of this failure is documented",
                   "operate several exchange rates at once, because the official rate had become "
                   "fiction and the banknote rate was the real price",
                   "devalue the official rate twice, on dated administrative acts"),
     "when": "the balance sheet twice monthly; the rate changes on decreed dates -- 2023-02-01 "
             "and 2023-11-01 are the two",
     "information": ("the true accessible reserve position versus the required reserves of banks",
                     "the real size of the balance-sheet gap",
                     "the Sayrafa book, which was never published"),
     "constraints": ("a sovereign in default since 2020-03-07",
                     "a banking system with no resolution framework",
                     "a gold holding that is legally difficult to sell",
                     "no IMF programme, only an unimplemented staff-level agreement"),
     "instruments": ("XAUUSD", "USDTRY", "EURTRY", "EURILS"),
     "counterparties": ("the depositors, whose dollars became 'lollars'",
                        "the commercial banks",
                        "the state, whose deficit it financed for a decade",
                        "the exchange-house market it could not control"),
     "observables": ("the bi-monthly reserve and gold lines",
                     "the official rate ladder (1,507.5 -> 15,000 -> 89,500)",
                     "the banknote rate and, while it ran, Sayrafa",
                     "currency in circulation, which exploded"),
     "impact": "THE REFERENCE CASE IN PEG FAILURE. Every stage has a date and a published "
               "document, which makes Lebanon the object against which every other peg in the "
               "desk's universe -- including the Danish one that has never failed -- can be "
               "measured",
     "persistence": "permanent: a peg that failed does not un-fail, and the post-2023 regime is "
                    "a different instrument from the pre-2019 one",
     "falsifier": "the dated collapse markers show no measurable effect on the regional risk "
                  "legs or on regional physical gold demand once the global risk complex and "
                  "the Turkish lira's own crisis over the same years are controlled for",
     "notes": "`lbp_official_rate` returns the administered rate in force on any date with the "
              "act that set it, so a Lebanese cell conditions on the step instead of pooling "
              "across three different instruments with one name"},
    {"name": "The Lebanese depositor as the holder of a frozen claim",
     "jurisdiction": "lb",
     "holds": "dollar deposits inside a banking system that will not pay them in dollars, and a "
              "cash economy that grew up beside it",
     "forced_to": ("accept a 'lollar' valuation far below a banknote dollar, or accept payout "
                   "schemes at administered rates",
                   "hold physical cash and gold instead of deposits, permanently",
                   "rely on remittances for the hard currency the banks cannot provide"),
     "when": "continuously since 2019-10-17; the informal capital controls have never been "
             "codified in law, which is itself a persistent fact",
     "information": ("which banks are paying and on what terms",
                     "the real discount on a deposit claim in the secondary market",
                     "the household's own remittance inflow"),
     "constraints": ("no deposit insurance that functions",
                     "no legal capital-control framework to appeal to",
                     "an economy that became cash-dollarised in practice"),
     "instruments": ("XAUUSD", "USDTRY", "EURILS"),
     "counterparties": ("the commercial banks", "the exchange houses",
                        "the diaspora, who send the hard currency",
                        "the gold market, which is the alternative store"),
     "observables": ("currency in circulation and the cash-dollar share",
                     "remittance inflows in the balance of payments",
                     "the banknote-to-lollar spread while it was quoted",
                     "the BSE index in pounds, which rose as a devaluation hedge"),
     "impact": "a fully cash-dollarised economy with no functioning banking system is a "
               "permanent physical-dollar and physical-gold demand centre; it is small in world "
               "terms and it is real, dated and legible",
     "persistence": "permanent on any horizon this desk tests",
     "falsifier": "the collapse markers show no measurable change in regional physical gold or "
                  "cash-dollar demand indicators once the world gold price and the regional "
                  "security environment are controlled for",
     "notes": "the BSE rising in pounds while the economy collapsed is the pack's clearest "
              "warning that a nominal local index is a currency statement, not an equity one"},
    {"name": "The Lebanese wheat importer and the destroyed Beirut silos",
     "jurisdiction": "lb",
     "holds": "near-total dependence on imported wheat, a milling sector concentrated at the "
              "port, and no significant strategic storage since 2020-08-04",
     "forced_to": ("import continuously and hold little, because the silos that held the "
                   "national reserve were destroyed in the port explosion",
                   "buy in hard currency it does not earn, at whichever rate is available",
                   "depend on subsidised finance and on World Bank-supported wheat facilities"),
     "when": "continuously, with tender and shipment cycles; the Ramadan and Eid seasons "
             "concentrate demand",
     "information": ("the real stock position, which is weeks rather than months",
                     "the financing available for the next cargo",
                     "the mills' own coverage"),
     "constraints": ("no storage at scale",
                     "a currency that cannot buy foreign wheat without support",
                     "one principal port with reduced capacity"),
     "instruments": ("WHEAT", "CORN", "SUGAR"),
     "counterparties": ("Black Sea and European wheat exporters",
                        "the World Bank and donors financing the purchases",
                        "the mills and bakeries under a subsidised bread price"),
     "observables": ("import tonnage in the trade statistics and in FAO/GIEWS briefs",
                     "the dated financing facilities",
                     "the subsidised bread price and its dated changes",
                     "WFP's priced food basket"),
     "impact": "a country with no reserve must buy on the spot calendar, so its demand is "
               "INELASTIC AND DATED; that is a small but clean demand-side observable for the "
               "wheat complex, and the 2020-08-04 destruction of the silos is the structural "
               "break that created it",
     "persistence": "years: the storage has not been rebuilt at scale",
     "falsifier": "Lebanese and Syrian import windows show no measurable effect on the wheat "
                  "complex at any horizon once Black Sea export policy and the global balance "
                  "are controlled for -- which is the expected result at this size and is worth "
                  "MEASURING rather than assuming",
     "notes": "the honest prior here is that the size is small; the reason to carry it is that "
              "the TIMING is exogenous and dated, which is rarer than size"},
    # ------------------------------------------------------------------ Syria
    {"name": "The Central Bank of Syria as a near-silent administrator of several rates",
     "jurisdiction": "sy",
     "holds": "an official rate reset by decree, a separate remittance rate, and a statistical "
              "apparatus that largely stopped publishing",
     "forced_to": ("set a remittance rate that is closer to the market, because remittances are "
                   "the economy's principal hard-currency inflow and will not come at the "
                   "official rate",
                   "reset the official rate periodically as the gap becomes untenable",
                   "operate through an institution whose external relationships are constrained "
                   "by comprehensive sanctions"),
     "when": "decrees are irregular and are announced when they happen; the 2024-12-08 "
             "transition is a boundary at which the institution itself changed",
     "information": ("the real reserve position, which is not published",
                     "the true remittance volume",
                     "the internal decision to reset"),
     "constraints": ("comprehensive sanctions on the financial system",
                     "an economy in which the state's writ and its statistics both contracted",
                     "no IMF Article IV since before the war"),
     "instruments": ("USDTRY", "XAUUSD", "WHEAT"),
     "counterparties": ("the licensed transfer companies",
                        "the diaspora sending remittances",
                        "the importers of wheat, fuel and medicine",
                        "Turkish and Lebanese trade counterparties"),
     "observables": ("the published official and remittance rates when they appear",
                     "the reported black-market rate",
                     "MIRROR customs from Turkey, Lebanon, Jordan and China",
                     "WFP's priced food basket, which is a real price series"),
     "impact": "a currency with several rates and no published reserve position cannot be "
               "modelled from its own data; it can only be read through its partners and its "
               "prices, which is exactly what this pack does and says it is doing",
     "persistence": "the multiplicity has persisted for more than a decade and the 2024-12-08 "
                    "transition reset the institutional arrangement rather than the structure",
     "falsifier": "mirror-derived Syrian import values show no relationship to the reported "
                  "parallel rate across the sample, which would mean the reported rate is not "
                  "the rate at which trade actually clears and the substitute must be replaced",
     "notes": "THE LIMIT CASE, DECLARED. Five source layers are named ABSENT for Syria with "
              "their substitutes; a Syrian cell cites the substitute or answers UNMEASURED"},
    {"name": "The Syrian wheat buyer and the Euphrates grain belt",
     "jurisdiction": "sy",
     "holds": "a country that was a wheat EXPORTER before 2011 and became a large importer, and "
              "a northeastern grain belt whose harvest is reported by agencies rather than by "
              "the state",
     "forced_to": ("import a structural deficit every year, financed in hard currency it does "
                   "not earn",
                   "buy through tenders and agency-financed purchases whose terms are reported "
                   "publicly even when the state's own figures are not",
                   "depend on a harvest that drought and the loss of irrigation have made "
                   "volatile"),
     "when": "the harvest is assessed in May and June; import tenders and agency purchases run "
             "through the year",
     "information": ("the real harvest and the real stock position",
                     "the financing available for the next purchase",
                     "the flows across the northern and Lebanese borders"),
     "constraints": ("sanctions that complicate payment even for exempt humanitarian trade",
                     "a fragmented territory with several buyers",
                     "irrigation and drought risk on the Euphrates"),
     "instruments": ("WHEAT", "COTTON", "USDTRY"),
     "counterparties": ("Black Sea exporters, principally Russian",
                        "the UN agencies financing purchases",
                        "Turkish and Lebanese border traders",
                        "the farmers of the northeast"),
     "observables": ("FAO/GIEWS harvest and import-requirement estimates",
                     "WFP's priced bread and food basket",
                     "MIRROR customs wheat flows from the reporting partners",
                     "reported procurement prices offered to farmers"),
     "impact": "a structural annual import requirement whose SIZE is estimated by agencies and "
               "whose TIMING is visible in mirror data; small in world terms and one of the "
               "cleanest cases the desk has of a demand series reconstructed entirely from "
               "lawful substitutes",
     "persistence": "annual and structural; the pre-2011 export position has not returned",
     "falsifier": "FAO-assessed Syrian harvest shortfalls show no relationship to mirror-reported "
                  "wheat imports in the following two quarters, which would mean the substitute "
                  "does not carry the information it is claimed to carry",
     "notes": "COTTON IS HERE FOR A REASON: the Euphrates cotton belt was a significant producer "
              "and its collapse is visible in the same mirror data, which makes it a second, "
              "independent test of whether the substitute works"},
    {"name": "The Syrian phosphate exporter and the Mediterranean ports",
     "jurisdiction": "sy",
     "holds": "large phosphate rock deposits at Khneifis and Sharqiya, and the ports of Tartus "
              "and Latakia through which the rock historically shipped",
     "forced_to": ("ship through a small number of Mediterranean berths under sanctions",
                   "operate under contract arrangements whose terms are not published",
                   "compete with Jordanian, Moroccan and Egyptian rock in the same market"),
     "when": "irregular; the shipments appear in partner customs returns rather than in Syrian "
             "publications",
     "information": ("actual extracted tonnage",
                     "the contractual arrangements and the realised price",
                     "the ports' real loading capacity"),
     "constraints": ("sanctions on the financial and shipping channels",
                     "infrastructure damage and underinvestment",
                     "a world market where it is a marginal supplier"),
     "instruments": ("CORN", "WHEAT", "COTTON"),
     "counterparties": ("the importers who report the cargoes on their own side",
                        "the shipping intermediaries",
                        "Jordanian and Moroccan producers as the competing supply"),
     "observables": ("MIRROR customs phosphate imports reported by partners",
                     "port call reporting in the public shipping press",
                     "world phosphate rock price indices as the reference"),
     "impact": "a marginal supplier whose absence tightened the phosphate market at the margin "
               "in the 2010s; the executable route is the same fertiliser-cost chain into the "
               "grain complex, with the Jordanian producer as the within-region control",
     "persistence": "years; the disruption has been structural rather than cyclical",
     "falsifier": "mirror-reported Syrian phosphate volumes show no relationship to world "
                  "phosphate prices or to the fertiliser-cost chain once Moroccan and Jordanian "
                  "supply and the ammonia (gas) cost are controlled for",
     "notes": "the JORDANIAN PRODUCER IS THE CONTROL and it is named: two phosphate exporters in "
              "one region, one sanctioned and one not, is a usable comparison"},
    # ------------------------------------------------------------------ shared
    {"name": "The Strait of Hormuz tanker owner and war-risk underwriter",
     "jurisdiction": "shared",
     "holds": "the vessels and the insurance that move roughly a fifth of world petroleum "
              "consumption through a two-mile-wide shipping lane bounded by Iran",
     "forced_to": ("price war risk continuously and re-price it within days of an incident",
                   "route through the strait, because for every Gulf loading point except "
                   "Oman's there is no alternative",
                   "publish nothing about individual cargoes, so the observable is the premium "
                   "and the freight rate rather than the shipment"),
     "when": "war-risk premiums re-price within days of a dated incident; freight responds "
             "within the same week",
     "information": ("the real premium being quoted to each owner",
                     "which owners have stopped transiting",
                     "the naval and escort arrangements in force"),
     "constraints": ("a single chokepoint with no bypass for most of the Gulf",
                     "an insurance market that can withdraw cover faster than any state can act",
                     "a reinsurance chain that transmits a local risk globally"),
     "instruments": ("XBRUSD", "XNGUSD", "USDJPY"),
     "counterparties": ("the Gulf producers and their buyers",
                        "the Asian refiners, above all in Japan, Korea, China and India",
                        "the marine insurance and reinsurance market"),
     "observables": ("dated incidents and the war-risk premium quoted after them",
                     "freight rates on the relevant routes",
                     "EIA transit volume estimates",
                     "loadings at the OUTSIDE-STRAIT ports, which are the control"),
     "impact": "a chokepoint event is one of the few remaining sources of a genuine oil risk "
               "premium; the JPY leg is here because Japan is among the most Hormuz-dependent "
               "large economies and the yen is the executable haven",
     "persistence": "days to weeks per incident unless the transit itself is interrupted",
     "falsifier": "dated Hormuz incidents show no measurable move in crude or in the yen once "
                  "the global risk complex is controlled for, and no divergence between "
                  "inside-strait and outside-strait loadings -- in which case the event was a "
                  "headline and not a chokepoint event",
     "notes": "THE BYPASS GEOGRAPHY BELONGS TO `gulf`, which owns Duqm, Ras Markaz and Sohar as "
              "the outside-strait control. This pack carries the RISK side only and uses the "
              "sibling's control rather than duplicating it"},
    {"name": "The Gulf employer of Levantine and Egyptian labour",
     "jurisdiction": "shared",
     "holds": "the jobs that several million Jordanians, Lebanese, Syrians, Palestinians and "
              "Egyptians hold, and therefore the hard-currency inflow that finances three of "
              "this pack's five economies",
     "forced_to": ("pay monthly, which makes the remittance a DATED month-end flow",
                   "hire and fire with the Gulf oil cycle, which transmits an oil price into a "
                   "Levantine balance of payments with a lag",
                   "remit through channels whose pricing is published"),
     "when": "monthly on the salary cycle, with pronounced Ramadan, Eid and summer peaks",
     "information": ("the real headcount by nationality",
                     "the hiring pipeline as projects are awarded",
                     "the corridor's own pricing and volume"),
     "constraints": ("the Gulf fiscal cycle, which follows the oil price",
                     "nationalisation policies that reduce expatriate hiring",
                     "visa and residency regimes that change by decree"),
     "instruments": ("XAUUSD", "EURUSD", "UK100"),
     "counterparties": ("the Jordanian, Lebanese and Syrian households receiving the money",
                        "the exchange houses and transfer operators",
                        "the receiving central banks, for whom this is the balance of payments"),
     "observables": ("remittance inflows in the balance-of-payments statistics",
                     "World Bank corridor pricing",
                     "the Gulf fiscal and hiring cycle",
                     "the month-end and Eid concentration in transfer volumes"),
     "impact": "an oil price change reaches the Levant primarily as a REMITTANCE change, not as "
               "an import-cost change; that is a slow, dated transmission from `gulf` and `sa` "
               "into this pack and it is the reason both are named in INTERACTIONS",
     "persistence": "quarters: the hiring response to an oil cycle lags by two to four quarters",
     "falsifier": "Gulf oil-cycle turns show no measurable effect on Levantine remittance "
                  "inflows at any lag once European diaspora flows and the receiving countries' "
                  "own conditions are controlled for",
     "notes": "the executable legs are the stores of value the money lands in -- gold and hard "
              "currency -- plus the European risk leg for the diaspora's other half"},
    {"name": "The UN agency and donor as a dated, published fiscal counterparty",
     "jurisdiction": "shared",
     "holds": "the refugee response plans, the funding appeals and the cash-transfer programmes "
              "that are a measurable share of the Jordanian, Lebanese and Syrian economies",
     "forced_to": ("publish the appeal, the requirement and the funding actually received, "
                   "because donor accountability requires it -- which makes a humanitarian "
                   "shock a DATED, PUBLISHED FISCAL EVENT",
                   "buy food and fuel locally and regionally, which is a real demand line",
                   "cut programmes when funding falls short, on announced dates"),
     "when": "appeals launch annually on dated days; funding levels are tracked continuously; "
             "programme cuts are announced",
     "information": ("the true registered population and its movement",
                     "the pledged-versus-received gap before it is published",
                     "the procurement pipeline"),
     "constraints": ("donor fatigue and competing global emergencies",
                     "host-government policy on work rights and registration",
                     "access constraints inside Syria"),
     "instruments": ("WHEAT", "SUGAR", "USDTRY"),
     "counterparties": ("the host governments of Jordan, Lebanon, Turkey and Iraq",
                        "the donor states",
                        "the local food and fuel suppliers",
                        "the registered population receiving transfers"),
     "observables": ("UNHCR registered population by country and month",
                     "OCHA FTS funding received against each appeal",
                     "dated programme-cut announcements",
                     "WFP procurement and transfer values"),
     "impact": "a funding shortfall is a measurable negative fiscal shock to a small open "
               "economy on a KNOWN DATE, which is a cleaner fiscal event than most budget "
               "processes produce anywhere",
     "persistence": "one appeal cycle, annual, with the cuts persisting until funding returns",
     "falsifier": "dated appeal shortfalls and programme cuts show no measurable effect on the "
                  "host economies' food import demand or on the regional risk legs once the "
                  "host countries' own fiscal positions are controlled for",
     "notes": "REFUGEE-DRIVEN FISCAL SHOCKS AS DATED PUBLISHED EVENTS is the whole point of this "
              "actor: the data is open, the dates are exact and almost nobody trades it"},
)
# --------------------------------------------------------------------------- domains
#: EIGHTEEN DOMAINS. Iraq owns A-D, Iran E-H, Jordan I-J, Lebanon K-L, Syria M-N, and O-R are the
#: shared mechanisms. Every jurisdiction owns at least two of its own, which is what stops this
#: from being one "Levant" domain with five flags on it.
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "OPECN-A", "title": "SOMO's monthly Basrah Official Selling Prices as a dated clock",
     "jurisdiction": "iq",
     "objects": ("the monthly differential for Basrah Medium and Basrah Heavy by destination",
                 "the ORDER of the Saudi and Iraqi announcements and the gap between them",
                 "the ministry's monthly export volume and revenue, which give realised price",
                 "the term-versus-spot share of each month's liftings"),
     "conditions": ("whether the Saudi OSP for the same month moved in the same direction",
                    "the Brent-Dubai relationship in the week before the announcement",
                    "whether the northern export route was flowing that month"),
     "instruments": ("XBRUSD", "XTIUSD", "USDINR"),
     "controls": ("the Saudi OSP announced days earlier, which separates 'Iraqi information' "
                  "from 'the regional reference'",
                  "matched months in which the differential was unchanged",
                  "a randomised-date null drawn from the same announcement week"),
     "notes": "AN ADMINISTERED PRICE WITH A DATE is a better research object than a traded one, "
              "because the announcement can be timed exactly and the counterfactual is the "
              "unchanged month"},
    {"id": "OPECN-B", "title": "The Kurdistan-Ceyhan shutdown: a court-dated supply shock",
     "jurisdiction": "iq",
     "objects": ("the 2023-03-25 halt following the ICC award against Turkey",
                 "roughly 450 kb/d of light crude removed from the seaborne market",
                 "every dated restart announcement and the volume that actually followed",
                 "the GAP between Erbil's published figures and Baghdad's for the same barrels"),
     "conditions": ("the pipeline state on the day (`kurdistan_pipeline_state`)",
                    "whether Iraqi FEDERAL exports rose in the same month",
                    "whether an OPEC+ decision landed in the same window"),
     "instruments": ("XBRUSD", "XTIUSD", "USDTRY"),
     "controls": ("Iraqi federal exports through Basrah over the same window, which separates "
                  "'Iraqi supply' from 'this pipeline'",
                  "matched months with no restart announcement",
                  "Mediterranean light-sour differentials against Atlantic-basin ones, which "
                  "separates a routing effect from a supply effect"),
     "notes": "A SUPPLY SHOCK WITH A COURT DATE ON IT. The award is published, the halt is "
              "dated, the volume is estimated by several independent parties, and the restart "
              "negotiations have been public throughout"},
    {"id": "OPECN-C", "title": "Iraq's OPEC+ quota, over-production and published compensation",
     "jurisdiction": "iq",
     "objects": ("the quota, the repeated over-production and the filed compensation schedules",
                 "the pledged under-production by named volume in named months",
                 "the realised export volume against the pledge",
                 "the fiscal pressure that makes compliance structurally hard"),
     "conditions": ("whether a compensation schedule was in force (`iraq_compensation_due`)",
                    "the realised Brent level relative to the budget's assumed price",
                    "whether the northern route was contributing volume"),
     "instruments": ("XBRUSD", "XTIUSD", "US500"),
     "controls": ("Saudi and UAE compliance over the same months, which separates 'Iraq' from "
                  "'the group'",
                  "matched months with no compensation schedule in force",
                  "the pre-2023 baseline period, when no schedule had been published"),
     "notes": "A DATED PROMISE WITH A MEASURABLE OUTCOME. The falsifier is built in: if exports "
              "do not fall in the pledged window, the promise was not a constraint"},
    {"id": "OPECN-D", "title": "The Iraqi dinar: an administered rate and a parallel premium",
     "jurisdiction": "iq",
     "objects": ("the 2023-02-07 revaluation from 1,460 to 1,320 by cabinet decision",
                 "the parallel rate in Baghdad and, separately, in Erbil",
                 "the premium and its response to dated US Treasury actions",
                 "the CBI auction's allocated volume and compliance rejection share"),
     "conditions": ("whether a dated US Treasury action landed in the preceding ten sessions",
                    "the premium regime (`parallel_premium` returns FRICTION, STRESS or failure)",
                    "whether the month contained a salary-cycle month end"),
     "instruments": ("XAUUSD", "USDTRY", "GBPTRY"),
     "controls": ("GBPTRY against USDTRY over the same window, which separates a DOLLAR move "
                  "from a LIRA move and stops an Iraqi claim from being a Turkish one",
                  "matched windows with no Treasury action",
                  "Jordanian dollarisation over the same months as the no-premium control"),
     "notes": "A DATED ADMINISTRATIVE ACT WITH A PUBLISHED CURRENCY EFFECT. The premium is a "
              "COMPLIANCE-FRICTION term before it is a devaluation expectation"},
    {"id": "OPECN-E", "title": "Iranian production as a function of dated US administrative acts",
     "jurisdiction": "ir",
     "objects": ("the JCPOA, the 2018-05-08 withdrawal, the 2019-05-02 waiver expiries and the "
                 "enforcement changes since",
                 "the export recovery and collapse that followed each",
                 "the Chinese independent refiner as the residual buyer",
                 "the mirror customs record of where the barrels actually went"),
     "conditions": ("the policy direction in force (`iran_policy_direction`)",
                    "whether an OPEC+ decision landed in the same quarter",
                    "the Brent-Dubai relationship at the time of the act"),
     "instruments": ("XBRUSD", "XTIUSD", "USDCNH"),
     "controls": ("OPEC+ decisions in the same quarters, which separate 'Iranian supply' from "
                  "'group supply'",
                  "matched quarters with no published act",
                  "Venezuelan sanctions episodes as the out-of-region analogue"),
     "notes": "THE EVENT IS PUBLISHED IN WASHINGTON, NOT TEHRAN, which is why this domain is "
              "testable at all and why every source it needs is a US government document"},
    {"id": "OPECN-F", "title": "The two OPEC series for Iran that disagree, and their gap",
     "jurisdiction": "ir",
     "objects": ("the direct-communication production table",
                 "the secondary-sources production table",
                 "the monthly GAP between them, which has run to hundreds of kb/d",
                 "the revisions each issue makes to prior months"),
     "conditions": ("the sign and size of the gap in the month",
                    "whether the gap widened or narrowed from the prior month",
                    "whether a dated US act fell in the same quarter"),
     "instruments": ("XBRUSD", "XTIUSD", "USDINR"),
     "controls": ("the same two tables for Iraq and Venezuela, which separates 'Iran' from 'the "
                  "measurement problem'",
                  "matched months with a small gap",
                  "the vintage of the print, since prior months are revised"),
     "notes": "ONE PUBLISHER, TWO CONTRADICTORY NUMBERS, SAME COVER DATE, EVERY MONTH, FREE. "
              "The disagreement is an observable about information, not a data-quality nuisance"},
    {"id": "OPECN-G", "title": "The rial lattice and the Bahar Azadi coin premium",
     "jurisdiction": "ir",
     "objects": ("the 42,000 official rate, the NIMA rates and the free market",
                 "the coin's published premium over its own metal content",
                 "the rotation between coins, dollars and Tehran equities",
                 "Shaparak card-transaction value as a nominal spending proxy"),
     "conditions": ("the official-to-free gap bucket",
                    "whether the window falls in the pre-Nowruz demand season",
                    "whether a dated sanctions act fell in the preceding month"),
     "instruments": ("XAUUSD", "XAGUSD", "USDTRY"),
     "controls": ("the world gold price and the dollar index, without which a local premium is "
                  "just the metal",
                  "Turkish domestic gold demand over the same windows as the regional control",
                  "matched non-Nowruz weeks in the same year"),
     "notes": "A PUBLISHED DOMESTIC INFLATION-EXPECTATION GAUGE denominated in a metal the box "
              "can trade; `coin_premium` computes it on the 7.3224 g / 900 purity basis"},
    {"id": "OPECN-H", "title": "South Pars, the winter gas deficit and fuel switching",
     "jurisdiction": "ir",
     "objects": ("the acknowledged pressure decline and deliverability limit at South Pars",
                 "the dated winter curtailment announcements",
                 "liquid-fuel burn in the power sector as the substitution",
                 "the Iraqi electricity shortfall that follows the Iranian supply cut"),
     "conditions": ("whether a curtailment was announced in the window",
                    "northern-hemisphere heating-degree days that winter",
                    "whether Iranian gas exports to Iraq or Turkey were interrupted"),
     "instruments": ("XNGUSD", "XBRUSD", "XTIUSD"),
     "controls": ("heating-degree days, without which every winter effect is weather",
                  "matched winters with no announced curtailment",
                  "Turkish gas import interruptions from other suppliers as the placebo"),
     "notes": "THE SECOND-LARGEST GAS RESERVE HOLDER IS SHORT GAS IN WINTER and therefore an OIL "
              "consumer in winter; the substitution is announced, which makes it an event"},
    {"id": "OPECN-I", "title": "Jordan's 0.709 peg as the control for a failed peg next door",
     "jurisdiction": "jo",
     "objects": ("thirty years of an unchanged parity through every regional shock",
                 "the CBJ-minus-Fed step at each decision",
                 "gross reserves and months of import cover",
                 "deposit dollarisation as the peg's thermometer"),
     "conditions": ("whether the window contains a regional shock that also hit Lebanon or Syria",
                    "the CBJ step relative to the Fed's at the nearest decision",
                    "whether an IMF review or a donor deposit landed in the window"),
     "instruments": ("EURUSD", "XAUUSD", "USDILS"),
     "controls": ("Lebanon over the identical windows, which is the treated unit to Jordan's "
                  "control -- same region, same decade, same shocks, opposite outcome",
                  "the Danish peg (`dk`) as the out-of-region peg that has also never failed",
                  "matched windows with no regional shock"),
     "notes": "A PEG THAT HOLDS NEXT DOOR TO A PEG THAT COLLAPSED IS AN IDENTIFICATION STRATEGY. "
              "The falsifier is symmetrical: if Jordan shows strain in the same windows, it is "
              "a treated unit and every paired test in this pack that uses it is invalid"},
    {"id": "OPECN-J", "title": "Dead Sea potash and phosphate in the fertiliser-cost chain",
     "jurisdiction": "jo",
     "objects": ("Jordanian potash and phosphate export tonnage and value, monthly",
                 "the annual and semi-annual contract settlements with Indian and Chinese buyers",
                 "Aqaba throughput and the Red Sea shipping-risk interruptions",
                 "the realised price derivable from tonnage and value"),
     "conditions": ("whether a contract settlement was announced in the window",
                    "the natural gas price regime, since ammonia is the competing input cost",
                    "whether Red Sea routing was disrupted in the window"),
     "instruments": ("CORN", "WHEAT", "SOYBEAN"),
     "controls": ("natural gas over the same windows, which separates 'potash' from 'ammonia'",
                  "the Belarusian and Russian supply share, which is the dominant world variable",
                  "matched windows with no settlement announcement"),
     "notes": "POTASH AND PHOSPHATE ARE NOT BROKER SYMBOLS AND THE PRODUCERS ARE NOT TRADABLE "
              "HERE: the lawful executable route is the fertiliser-cost chain into the grain "
              "complex, with the two dominant confounders named in the controls"},
    {"id": "OPECN-K", "title": "The dated anatomy of a peg failure",
     "jurisdiction": "lb",
     "objects": ("the official-rate ladder 1,507.5 -> 15,000 -> 89,500 with its two act dates",
                 "the banknote rate, Sayrafa and the 'lollar' as three simultaneous prices",
                 "the 2020-03-07 eurobond default",
                 "the BdL reserve and gold lines through the collapse"),
     "conditions": ("the rate regime in force (`lbp_official_rate` returns it with the act)",
                    "which collapse marker the window sits between",
                    "whether the Turkish lira was in its own crisis in the same window"),
     "instruments": ("XAUUSD", "USDTRY", "EURTRY", "EURILS"),
     "controls": ("JORDAN over the identical windows -- same region, same shocks, no devaluation",
                  "the Danish peg (`dk`) as the never-failed control that fixes the other end "
                  "of the scale",
                  "the Turkish lira's own crisis years, which must be excluded or the Lebanese "
                  "signal is measuring Ankara"),
     "notes": "THE DESK'S REFERENCE CASE IN PEG FAILURE, and the only one in which every stage "
              "has a published date. Pooling across the 2023-02-01 and 2023-11-01 steps measures "
              "three different administered instruments under one name"},
    {"id": "OPECN-L", "title": "Levantine wheat dependence and the destroyed Beirut silos",
     "jurisdiction": "lb",
     "objects": ("the 2020-08-04 destruction of the national grain reserve",
                 "import tonnage and the financing facilities that paid for it",
                 "the subsidised bread price and its dated changes",
                 "WFP's priced food basket as the outcome series"),
     "conditions": ("whether the window is before or after 2020-08-04",
                    "whether a donor-financed wheat facility was active",
                    "whether the window falls inside Ramadan"),
     "instruments": ("WHEAT", "CORN", "SUGAR"),
     "controls": ("Jordan's import pattern over the same windows, which has storage and a "
                  "working currency",
                  "Black Sea export-policy events, which dominate the world price",
                  "matched non-Ramadan windows in the same year"),
     "notes": "THE HONEST PRIOR IS THAT THE SIZE IS SMALL. The reason to carry it is that the "
              "TIMING is exogenous and dated, and a small effect with exact timing is testable "
              "where a large effect with vague timing is not"},
    {"id": "OPECN-M", "title": "The absent-statistics limit case and its mirror substitutes",
     "jurisdiction": "sy",
     "objects": ("what stopped being published, and when",
                 "MIRROR customs from Turkey, Lebanon, Jordan and China as the substitute",
                 "FAO/GIEWS harvest assessments and WFP priced baskets",
                 "the cotton and wheat series reconstructed entirely from partner reports"),
     "conditions": ("whether the window is before or after the 2024-12-08 transition",
                    "whether the reporting partner revised its own figures",
                    "whether the agency assessment for that season exists at all"),
     "instruments": ("WHEAT", "COTTON", "USDTRY"),
     "controls": ("the same mirror method applied to JORDAN, whose own statistics are complete, "
                  "which measures how much the mirror loses when the truth is known",
                  "matched pre-2011 years when Syria still published",
                  "the reporting partners' own revisions as the noise floor"),
     "notes": "THE PACK'S MEASURED REFUSAL, MADE TESTABLE. Validating the mirror against Jordan "
              "-- where both the mirror and the truth exist -- is what turns a substitute into "
              "an estimator with a known error rather than a hope"},
    {"id": "OPECN-N", "title": "The Syrian pound's multiple rates across a dated transition",
     "jurisdiction": "sy",
     "objects": ("the official rate, the remittance rate and the reported black-market rate",
                 "the 2024-12-08 transition as a boundary in what is published at all",
                 "the calendar change itself: holidays abolished and added by the new order",
                 "mirror-derived import values as the check on which rate trade clears at"),
     "conditions": ("whether the window crosses 2024-12-08",
                    "which rate the observation is denominated in",
                    "whether a rate decree landed in the window"),
     "instruments": ("USDTRY", "XAUUSD", "WHEAT"),
     "controls": ("the Turkish lira over the same windows, since Turkey is the dominant trade "
                  "partner and a lira move is not a Syrian event",
                  "mirror-derived unit values, which price the trade independently of any "
                  "reported rate",
                  "matched windows with no decree"),
     "notes": "A SERIES THAT LOOKS CONTINUOUS ACROSS 2024-12-08 HAS BEEN STITCHED BY SOMEBODY "
              "and the stitch is not published; this domain conditions on the boundary"},
    {"id": "OPECN-O",
     "title": "The Strait of Hormuz as the shared RISK, the control held elsewhere",
     "jurisdiction": "shared",
     "objects": ("dated incidents and the war-risk premium quoted after them",
                 "freight rates on the relevant routes",
                 "EIA transit volume estimates and the destination split",
                 "the inside-versus-outside-strait loading divergence"),
     "conditions": ("whether a dated incident fell in the window",
                    "whether outside-strait loadings moved in the same window",
                    "the global risk regime at the time"),
     "instruments": ("XBRUSD", "XNGUSD", "USDJPY"),
     "controls": ("the outside-strait loading points, WHICH BELONG TO `gulf` -- Duqm, Ras Markaz "
                  "and Sohar -- and are used here rather than duplicated",
                  "the global risk complex, without which every incident is a risk-off day",
                  "matched windows with a regional headline but no shipping consequence"),
     "notes": "THIS PACK CARRIES THE RISK SIDE ONLY. `gulf` owns the bypass geography and the "
              "within-country Mina al-Fahal control; duplicating them would double-count the "
              "same control across two packs and spend trial budget twice on one fact"},
    {"id": "OPECN-P", "title": "The Arab Gas Pipeline and Levantine power interconnection",
     "jurisdiction": "shared",
     "objects": ("Egyptian gas to Jordan, and onward to Syria and Lebanon when it flows",
                 "Israeli gas supply to Jordan under the published agreement",
                 "NEPCO's gas received and generation by fuel",
                 "the dated interruptions and restart announcements"),
     "conditions": ("whether the pipeline's Levantine legs were flowing in the window",
                    "the European gas price regime, which competes for Egyptian molecules",
                    "whether a dated supply agreement or interruption landed in the window"),
     "instruments": ("XNGUSD", "GER40", "USDILS"),
     "controls": ("European gas prices, which determine whether Egypt exports or diverts",
                  "matched windows with no interruption",
                  "Jordanian generation by fuel, which shows the substitution directly"),
     "notes": "A PHYSICAL INTERCONNECTION WITH DATED INTERRUPTIONS across four states, two of "
               "them sanctioned; the executable legs are the gas complex, the European risk leg "
               "and the shekel, and the Syrian leg's intermittency is itself the observable"},
    {"id": "OPECN-Q", "title": "The Levant's remittance dependence on the Gulf and the diaspora",
     "jurisdiction": "shared",
     "objects": ("remittance inflows to Jordan, Lebanon and Syria in the balance of payments",
                 "the Gulf hiring cycle and its lag behind the oil price",
                 "World Bank corridor pricing as the transaction-cost series",
                 "the month-end, Ramadan and Eid concentration in transfer volumes"),
     "conditions": ("the Gulf fiscal cycle stage relative to the oil price",
                    "whether the window contains a month end or an Eid",
                    "whether the receiving country was in its own crisis"),
     "instruments": ("XAUUSD", "EURUSD", "UK100"),
     "controls": ("the EUROPEAN diaspora corridors over the same windows, which separate 'Gulf "
                  "oil cycle' from 'diaspora income generally'",
                  "matched non-Eid month ends",
                  "Jordan as the recipient whose currency does not move, isolating the flow "
                  "from the exchange-rate response"),
     "notes": "AN OIL PRICE REACHES THE LEVANT AS A REMITTANCE CHANGE, with a two-to-four "
               "quarter lag; that is the slow transmission from `gulf` and `sa` into this pack "
               "and it is why both are named in INTERACTIONS"},
    {"id": "OPECN-R", "title": "Refugee-driven fiscal shocks as dated, published events",
     "jurisdiction": "shared",
     "objects": ("UNHCR registered population by country and month",
                 "the annual response plans, their requirements and the funding received",
                 "dated programme-cut announcements when funding falls short",
                 "the host states' own fiscal statements about the burden"),
     "conditions": ("whether an appeal launch or a funding-shortfall cut fell in the window",
                    "the host country's own fiscal position at the time",
                    "whether a dated policy change on work rights or registration landed"),
     "instruments": ("WHEAT", "SUGAR", "USDTRY"),
     "controls": ("the host countries' own fiscal cycles, without which a shortfall is a budget "
                  "season",
                  "matched windows with a fully funded appeal",
                  "Turkey's hosting burden and the EU arrangement as the large-country "
                  "comparison"),
     "notes": "A FUNDING SHORTFALL IS A NEGATIVE FISCAL SHOCK ON A KNOWN DATE to a small open "
              "economy -- cleaner timing than most budget processes anywhere produce, and the "
              "data is open"},
)
# --------------------------------------------------------------------------- the pack's miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "opecn_osp_clock", "domain_ids": ("OPECN-A", "OPECN-C"), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.opec_north.pack:mine_osp_clock",
     "needs": ("SOMO:osp_basrah_differential", "the Saudi OSP announcement date",
               "XBRUSD, XTIUSD D1 bars"),
     "notes": "emits the monthly announcement clock and the compensation schedules together; "
              "the Saudi reference is named as a requirement and reported UNMEASURED when absent"},
    {"name": "opecn_pipeline_state", "domain_ids": ("OPECN-B",), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.opec_north.pack:mine_pipeline_state",
     "needs": ("KURDISTAN_PIPELINE", "Iraqi federal export volumes", "XBRUSD D1 bars"),
     "notes": "emits the dated pipeline state transitions; the federal-export control is named "
              "as a requirement because without it a routing event reads as a supply event"},
    {"name": "opecn_rate_lattice", "domain_ids": ("OPECN-D", "OPECN-G", "OPECN-K", "OPECN-N"),
     "kind": "mechanism", "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.opec_north.pack:mine_rate_lattice",
     "needs": ("CURRENCIES", "the parallel-rate series for IQD, IRR, LBP and SYP (ABSENT here)",
               "XAUUSD, USDTRY D1 bars"),
     "notes": "emits each currency's regime and the premium machinery; the parallel series are "
              "not carried on this tree, so the miner emits the REGIME and the named absence "
              "rather than a premium it cannot compute"},
    {"name": "opecn_sanctions_clock", "domain_ids": ("OPECN-E", "OPECN-F"), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.opec_north.pack:mine_sanctions_clock",
     "needs": ("IRAN_SANCTIONS_ACTS", "the two OPEC production tables", "XBRUSD D1 bars"),
     "notes": "emits the dated US administrative acts as an event clock; every one is a "
              "published US government document and none touches a sanctioned system"},
    {"name": "opecn_calendar", "domain_ids": ("OPECN-G", "OPECN-L", "OPECN-Q"),
     "kind": "calendar", "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.opec_north.pack:mine_calendar",
     "needs": ("the derived Nowruz and Solar Hijri boundary", "both Easter computi",
               "LUNAR_HOLIDAYS", "XAUUSD, WHEAT H1 bars"),
     "notes": "THE DISTINGUISHING MINER OF THIS PACK: it emits the equinox-derived Iranian year, "
              "the two Lebanese computi and the four weekend regimes, and reports how few days a "
              "week all five states are open"},
    {"name": "opecn_mirror_substitutes", "domain_ids": ("OPECN-M", "OPECN-N"), "kind": "transfer",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.opec_north.pack:mine_mirror_substitutes",
     "needs": ("the declared layer absences", "UN Comtrade and partner customs (not carried)"),
     "notes": "emits the measured refusals: every absent layer with its jurisdiction, its reason "
              "and its named lawful substitute, so a downstream study cites the substitute or "
              "answers UNMEASURED"},
    {"name": "opecn_transmission_seeds",
     "domain_ids": ("OPECN-A", "OPECN-B", "OPECN-E", "OPECN-J", "OPECN-O", "OPECN-P", "OPECN-Q"),
     "kind": "transfer", "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.opec_north.pack:mine_transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED",),
     "notes": "the pack's map as HYPOTHESIS discoveries, deduplicated by the registry"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("OPECN-D", "OPECN-I"),
    "release_surprise": ("OPECN-A", "OPECN-F"),
    "calendar_settlement": ("OPECN-A", "OPECN-C"),
    "holiday_liquidity": ("OPECN-G", "OPECN-L"),
    "positioning": ("OPECN-I",),
    "carry_funding": ("OPECN-I", "OPECN-K"),
    "corporate_flow": ("OPECN-J", "OPECN-B"),
    "institutional_flow": ("OPECN-I", "OPECN-Q"),
    "equity_mechanics": ("OPECN-K",),
    "derivatives_expiry": ("OPECN-O",),
    "failure": ("OPECN-K", "OPECN-O"),
    "residual": ("OPECN-M", "OPECN-N"),
    "transfer": ("OPECN-P", "OPECN-Q"),
    "scouts": ("OPECN-M", "OPECN-R"),
    "session_microstructure": ("OPECN-G", "OPECN-H"),
}

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "OPECN-E1", "source": "SOMO's monthly Basrah OSP differential announcement",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD"), "to_country": "global", "sign": "+",
     "mechanism": "an administered differential on roughly 3.5 mb/d of seaborne sour crude is a "
                  "dated statement about Asian demand strength by the second-largest OPEC "
                  "producer; the ANNOUNCEMENT is the information, not the cargo",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "SOMO", "constraint": "the Saudi OSP is announced first and anchors the region",
     "flow": "administered price into the sour complex",
     "condition": "an OSP change in the opposite direction to the Saudi one announced days before",
     "control": "the Saudi OSP for the same month; matched months with no change",
     "falsifier": "Basrah OSP change months show no move in the Brent-Dubai relationship once "
                  "the Saudi announcement is controlled for",
     "evidence": "HYPOTHESIS"},
    {"id": "OPECN-E2", "source": "the Kurdistan-Ceyhan pipeline state (shut since 2023-03-25)",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD", "USDTRY"), "to_country": "global",
     "sign": "+",
     "mechanism": "a court-dated removal of roughly 450 kb/d of light crude from the seaborne "
                  "market tightens Mediterranean light-sour differentials; each dated restart "
                  "announcement is the same event with the sign reversed",
     "horizon": "0 to 20 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the KRG Ministry of Natural Resources and the Turkish transit operator",
     "constraint": "an ICC award that made accepting the crude a liability",
     "flow": "physical supply withdrawal and its restoration",
     "condition": "a dated halt or restart announcement with no offsetting federal export move",
     "control": "Iraqi federal exports through Basrah over the same window; Atlantic-basin "
                "differentials as the non-Mediterranean comparison",
     "falsifier": "the 2023-03-25 halt and each restart announcement show no measurable effect "
                  "once federal exports in the same month are controlled for",
     "evidence": "HYPOTHESIS"},
    {"id": "OPECN-E3", "source": "Iraq's published OPEC+ compensation schedules",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD"), "to_country": "global", "sign": "+",
     "mechanism": "a dated promise to under-produce by a named volume in named months is a "
                  "commitment whose credibility the market prices; a promise from a producer "
                  "with a salary-bill constraint is priced at a discount",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the Iraqi Ministry of Finance and SOMO",
     "constraint": "a fiscal breakeven that makes volume politically compulsory",
     "flow": "committed supply reduction, credible or not",
     "condition": "a new or re-tabled schedule while Brent sits below the budget's assumed price",
     "control": "Saudi and UAE compliance in the same months; matched months with no schedule",
     "falsifier": "compensation-schedule months show no measurable change in Iraqi exports and "
                  "no measurable price response, which would make the schedule an announcement "
                  "without a mechanism",
     "evidence": "HYPOTHESIS"},
    {"id": "OPECN-E4", "source": "dated US Treasury actions on the Iraqi dollar channel",
     "target": "XAUUSD", "targets": ("XAUUSD", "USDTRY", "GBPTRY"), "to_country": "iq",
     "sign": "+",
     "mechanism": "a compliance action rations access to the official rate, the parallel premium "
                  "widens, and households and merchants rotate into physical dollars and gold; "
                  "the gold leg is the executable end of a plumbing event",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 2.0,
     "actor": "the Central Bank of Iraq and the Iraqi household",
     "constraint": "correspondent access depends on the compliance regime",
     "flow": "retail rotation into hard assets",
     "condition": "a dated Treasury action with no offsetting rise in auction allocation",
     "control": "GBPTRY against USDTRY, separating a dollar move from a lira move; matched "
                "windows with no Treasury action",
     "falsifier": "dated Treasury actions show no widening of the parallel premium and no rise "
                  "in regional physical gold demand in the following ten sessions",
     "evidence": "HYPOTHESIS"},
    {"id": "OPECN-E5", "source": "dated US administrative acts on Iranian oil sanctions",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD", "USDCNH"), "to_country": "global",
     "sign": "-",
     "mechanism": "a relaxation adds up to a million barrels a day to seaborne supply within "
                  "quarters and a tightening removes it; the act is published on a known day in "
                  "Washington and the supply response is the thing being measured",
     "horizon": "1 to 4 quarters", "horizon_class": "multi_day", "lag_days": 60.0,
     "actor": "NIOC and the US Treasury",
     "constraint": "a small set of willing buyers concentrated in Chinese independent refiners",
     "flow": "administratively gated supply",
     "condition": "a published act with no OPEC+ decision in the same quarter",
     "control": "OPEC+ decisions in the same quarters; Venezuelan sanctions episodes as the "
                "out-of-region analogue",
     "falsifier": "the dated acts show no measurable effect on Brent term structure in the "
                  "following quarter once OPEC+ decisions are controlled for",
     "evidence": "HYPOTHESIS"},
    {"id": "OPECN-E6", "source": "the gap between OPEC's two Iranian production series",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD"), "to_country": "global", "sign": "+",
     "mechanism": "when the direct-communication figure exceeds the secondary-sources figure by "
                  "an unusual margin, the market's own trackers are finding less oil than the "
                  "state claims; the DISAGREEMENT is information about supply visibility",
     "horizon": "0 to 20 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the OPEC Secretariat and the secondary-source trackers",
     "constraint": "neither table is auditable and both are published anyway",
     "flow": "information about the reliability of a supply estimate",
     "condition": "a monthly gap in the top decile of its own history",
     "control": "the same two tables for Iraq and Venezuela, which separates Iran from the "
                "measurement problem; vintage-matched prints",
     "falsifier": "large-gap months show no measurable effect on crude or its term structure "
                  "relative to small-gap months in the same regime",
     "evidence": "HYPOTHESIS"},
    {"id": "OPECN-E7", "source": "the Bahar Azadi coin premium and the free-market rial",
     "target": "XAUUSD", "targets": ("XAUUSD", "XAGUSD"), "to_country": "ir", "sign": "+",
     "mechanism": "a widening premium is a published statement that Iranian households expect "
                  "more inflation and are bidding for physical metal; Iran is a material "
                  "regional physical-demand centre and the effect, if any, is a demand-side one",
     "horizon": "1 to 4 weeks", "horizon_class": "multi_day", "lag_days": 3.0,
     "actor": "the Iranian household", "constraint": "no access to any foreign financial product",
     "flow": "domestic physical demand for gold",
     "condition": "a premium in the top quartile with the world gold price flat",
     "control": "the world gold price and the dollar index; Turkish domestic demand as the "
                "regional control; matched non-Nowruz weeks",
     "falsifier": "coin-premium spikes show no measurable relationship to regional physical "
                  "demand or to gold once the world price, the dollar and the Nowruz season are "
                  "controlled for -- the expected result at this size, and worth measuring",
     "evidence": "HYPOTHESIS"},
    {"id": "OPECN-E8", "source": "dated Iranian winter gas curtailment announcements",
     "target": "XNGUSD", "targets": ("XNGUSD", "XBRUSD", "XTIUSD"), "to_country": "global",
     "sign": "+",
     "mechanism": "curtailment forces liquid-fuel burn in power generation and cuts gas exports "
                  "to Iraq and Turkey, so a gas-reserve giant becomes a marginal oil consumer "
                  "and a regional gas shortfall in the same weeks",
     "horizon": "2 to 8 weeks", "horizon_class": "multi_day", "lag_days": 7.0,
     "actor": "the Iranian power and gas balancer",
     "constraint": "subsidised domestic prices and an acknowledged deliverability limit",
     "flow": "fuel substitution and export interruption",
     "condition": "a dated curtailment announcement in a cold window",
     "control": "heating-degree days, without which every winter effect is weather; matched "
                "winters with no announcement",
     "falsifier": "announced curtailments show no measurable effect on the gas or crude complex "
                  "once heating-degree days are controlled for",
     "evidence": "HYPOTHESIS"},
    {"id": "OPECN-E9", "source": "Jordanian potash and phosphate contract settlements and tonnage",
     "target": "CORN", "targets": ("CORN", "WHEAT", "SOYBEAN"), "to_country": "global",
     "sign": "+",
     "mechanism": "fertiliser cost is an input to planting economics; a settlement that raises "
                  "the potash contract price raises the cost of the next planting and, at the "
                  "margin, the acreage and yield decision",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 45.0,
     "actor": "Arab Potash and JPMC", "constraint": "a world price set by much larger producers",
     "flow": "input cost into the grain complex",
     "condition": "a settlement announcement with natural gas flat in the same window",
     "control": "natural gas, which is the ammonia input and the dominant confounder; the "
                "Belarusian and Russian supply share; matched windows with no settlement",
     "falsifier": "settlement and tonnage changes show no effect on the grain complex once gas "
                  "and the Belarus/Russia share are controlled for -- in which case this is a "
                  "gas story wearing a Jordanian label and the edge is retired",
     "evidence": "HYPOTHESIS"},
    {"id": "OPECN-E10", "source": "the dated Lebanese peg-failure markers",
     "target": "XAUUSD", "targets": ("XAUUSD", "USDTRY", "EURTRY"), "to_country": "lb",
     "sign": "+",
     "mechanism": "a completed peg failure with published dates is a regional confidence event; "
                  "the executable legs are the regional currency-crisis basket and the store of "
                  "value the population actually moved into",
     "horizon": "0 to 20 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "Banque du Liban and the Lebanese depositor",
     "constraint": "a sovereign in default with no resolution framework",
     "flow": "confidence and physical store-of-value demand",
     "condition": "a dated marker with the Turkish lira not in its own crisis window",
     "control": "JORDAN over identical windows as the peg that held; `dk` as the never-failed "
                "control; Turkish domestic crisis windows excluded",
     "falsifier": "the dated collapse markers show no measurable effect on the regional risk "
                  "legs once the global risk complex and Turkey's own crisis are controlled for",
     "evidence": "HYPOTHESIS"},
    {"id": "OPECN-E11", "source": "Levantine wheat import tenders and agency-financed purchases",
     "target": "WHEAT", "targets": ("WHEAT", "CORN", "SUGAR"), "to_country": "global",
     "sign": "+",
     "mechanism": "two economies with almost no storage must buy on the spot calendar, so their "
                  "demand is inelastic and DATED; the size is small and the timing is exogenous",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 2.0,
     "actor": "the Lebanese and Syrian wheat buyers",
     "constraint": "no strategic storage since 2020-08-04 in Lebanon; no hard currency in Syria",
     "flow": "inelastic import demand on announced dates",
     "condition": "a tender or financed purchase outside a Black Sea policy window",
     "control": "Black Sea export-policy events, which dominate the world price; Jordan's "
                "pattern as the with-storage comparison; matched non-Ramadan windows",
     "falsifier": "tender windows show no measurable effect on the wheat complex at any horizon, "
                  "which is the expected result at this size and is worth measuring rather than "
                  "assuming",
     "evidence": "HYPOTHESIS"},
    {"id": "OPECN-E12", "source": "dated Strait of Hormuz incidents and the war-risk premium",
     "target": "XBRUSD", "targets": ("XBRUSD", "XNGUSD", "USDJPY"), "to_country": "global",
     "sign": "+",
     "mechanism": "a chokepoint event raises the insurance and freight cost of every Gulf cargo "
                  "at once and bids the haven currency of the most Hormuz-dependent large "
                  "economy; an event that moves headlines but not loadings is not this event",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the tanker owner and the war-risk underwriter",
     "constraint": "no bypass for any Gulf loading point except Oman's",
     "flow": "risk premium into freight, crude and the haven leg",
     "condition": "an incident with a measurable shipping consequence",
     "control": "THE OUTSIDE-STRAIT LOADINGS, WHICH BELONG TO `gulf` and are used here rather "
                "than duplicated; the global risk complex; headline-only windows",
     "falsifier": "dated incidents show no divergence between inside- and outside-strait "
                  "loadings and no crude or yen move once the global risk complex is controlled",
     "evidence": "HYPOTHESIS"},
    {"id": "OPECN-E13", "source": "Arab Gas Pipeline and Israeli-Jordanian gas supply changes",
     "target": "XNGUSD", "targets": ("XNGUSD", "GER40", "USDILS"), "to_country": "global",
     "sign": "+",
     "mechanism": "an interruption forces Jordanian and Lebanese fuel switching and diverts "
                  "Egyptian molecules; when European prices are high, Egypt exports LNG instead "
                  "of piping gas east, so the European price is the switch",
     "horizon": "2 to 8 weeks", "horizon_class": "multi_day", "lag_days": 7.0,
     "actor": "NEPCO and the Egyptian and Israeli suppliers",
     "constraint": "a pipeline that crosses Syria and an interconnection that is political",
     "flow": "physical gas rerouting and fuel substitution",
     "condition": "a dated interruption or supply agreement with European prices in a known "
                  "regime",
     "control": "European gas prices, which determine the diversion; Jordanian generation by "
                "fuel, which shows the substitution directly; matched no-interruption windows",
     "falsifier": "dated interruptions show no measurable effect on the gas complex or on "
                  "Jordanian generation mix once European prices are controlled for",
     "evidence": "HYPOTHESIS"},
    {"id": "OPECN-E14", "source": "the Gulf hiring cycle and Levantine remittance inflows",
     "target": "XAUUSD", "targets": ("XAUUSD", "EURUSD", "UK100"), "to_country": "shared",
     "sign": "+",
     "mechanism": "an oil price change alters Gulf hiring with a two-to-four quarter lag and "
                  "therefore Levantine hard-currency inflows; the money lands in stores of value "
                  "rather than in local deposits, because the local banks are not trusted",
     "horizon": "2 to 4 quarters", "horizon_class": "multi_day", "lag_days": 180.0,
     "actor": "the Gulf employer and the receiving household",
     "constraint": "nationalisation policies and visa regimes that change by decree",
     "flow": "remittance income into physical stores of value",
     "condition": "a Gulf fiscal-cycle turn with the European diaspora corridors flat",
     "control": "the EUROPEAN diaspora corridors, which separate the Gulf oil cycle from "
                "diaspora income generally; Jordan as the no-devaluation recipient",
     "falsifier": "Gulf oil-cycle turns show no measurable effect on Levantine remittance "
                  "inflows at any lag once European corridors and the receiving countries' own "
                  "conditions are controlled for",
     "evidence": "HYPOTHESIS"},
    {"id": "OPECN-E15", "source": "UNHCR and OCHA appeal shortfalls and dated programme cuts",
     "target": "WHEAT", "targets": ("WHEAT", "SUGAR", "USDTRY"), "to_country": "shared",
     "sign": "-",
     "mechanism": "a funding shortfall removes a measurable share of demand for food and fuel "
                  "from three small open economies on a KNOWN DATE, and shifts the burden onto "
                  "host budgets that are already constrained",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the UN agency and the donor states",
     "constraint": "donor fatigue and competing global emergencies",
     "flow": "financed import demand, withdrawn on an announced date",
     "condition": "a dated cut announcement with the host country's own fiscal position stable",
     "control": "the host countries' own fiscal cycles; matched fully funded appeal windows; "
                "Turkey's hosting burden as the large-country comparison",
     "falsifier": "dated shortfalls and cuts show no measurable effect on host-country food "
                  "import demand or on the regional legs once host fiscal positions are "
                  "controlled for",
     "evidence": "HYPOTHESIS"},
)
# --------------------------------------------------------------------------- policy eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "the Lebanese peg that held", "start": "1997-12-22", "end": "2019-10-16",
     "regime": "1,507.5 to the dollar, defended for twenty-two years by paying above-market "
               "rates on dollar deposits and recycling them into the sovereign and the central "
               "bank; the arrangement was solvent only while new deposits arrived",
     "markers": ("1997-12 the peg is set", "2016 the large 'financial engineering' operations"),
     "why_it_matters": "OPECN-K's state variable CANNOT VARY here; pooling this era with the "
                       "collapse measures a peg and a default together and calls it one series",
     "status": "SETTLED"},
    {"name": "the JCPOA relief window", "start": "2016-01-16", "end": "2018-05-07",
     "regime": "nuclear-related sanctions lifted on Implementation Day; Iranian exports recover "
               "toward 2.5 mb/d within a year and the two OPEC series converge",
     "markers": ("2015-07-14 the agreement", "2016-01-16 Implementation Day"),
     "why_it_matters": "the only window in the modern sample in which Iranian supply is a "
                       "geological and commercial variable rather than an administrative one",
     "status": "SETTLED"},
    {"name": "maximum pressure", "start": "2018-05-08", "end": "2021-01-19",
     "regime": "the US withdraws from the JCPOA, oil sanctions snap back on 2018-11-05 with "
               "180-day waivers, and the waivers are allowed to expire on 2019-05-02; exports "
               "fall to a few hundred thousand barrels a day and the two OPEC series diverge",
     "markers": ("2018-05-08 the withdrawal", "2018-11-05 snapback",
                 "2019-05-02 the waivers expire"),
     "why_it_matters": "OPECN-E and OPECN-F's sharpest identification: three dated acts in "
                       "eighteen months with a measurable supply response after each",
     "status": "SETTLED"},
    {"name": "the Lebanese collapse", "start": "2019-10-17", "end": "2023-10-31",
     "regime": "protests, informal capital controls, the first sovereign default in the "
               "country's history, the port explosion, Sayrafa, and two devaluations of the "
               "official rate; three simultaneous exchange rates for most of it",
     "markers": ("2019-10-17 the protests", "2020-03-07 the eurobond default",
                 "2020-08-04 the port explosion", "2023-02-01 the rate moves to 15,000"),
     "why_it_matters": "THE ERA THAT INVALIDATES ANY POOLED LEBANESE STUDY: the official rate, "
                       "the banknote rate and the deposit rate were three different instruments "
                       "with one name, and the grain reserve ceased to exist inside it",
     "status": "SETTLED"},
    {"name": "the Iraqi dollar-channel tightening", "start": "2022-11-15", "end": "2024-12-31",
     "regime": "outward transfers move onto a screened compliance platform, the official rate is "
               "revalued to 1,320 on 2023-02-07, and cash dollar transactions are progressively "
               "banned; the parallel premium widens and then partially narrows as banks adapt",
     "markers": ("2022-11 the platform requirement", "2023-02-07 the revaluation to 1,320",
                 "2024-01 the ban on cash dollar transactions"),
     "why_it_matters": "OPECN-D's treatment window; the premium before and after is a different "
                       "object because the rationing mechanism changed",
     "status": "SETTLED"},
    {"name": "the Kurdistan-Ceyhan shutdown", "start": "2023-03-25", "end": "2025-09-26",
     "regime": "the ICC award against Turkey halts roughly 450 kb/d of northern exports; the "
               "KRG's fiscal position deteriorates, trucked exports partially substitute, and "
               "every announced restart deadline passes",
     "markers": ("2023-03-25 the halt", "2023-2025 repeated failed restart announcements"),
     "why_it_matters": "OPECN-B's treatment window, and the cleanest court-dated supply "
                       "experiment in the pack",
     "status": "SETTLED"},
    {"name": "the Syrian transition", "start": "2024-12-08", "end": "2026-12-31",
     "regime": "the political order changes, the publishing institutions change with it, "
               "holidays are abolished and added by decree, and what data exists at all is a "
               "different set before and after; sanctions relief is partial and dated",
     "markers": ("2024-12-08 the transition", "2025-12-08 the first anniversary added to the "
                 "national calendar while 8 March and 6 October were dropped"),
     "why_it_matters": "OPECN-M and OPECN-N's boundary. A Syrian series that looks continuous "
                       "across this date has been stitched by somebody and the stitch is not "
                       "published",
     "status": "OPEN"},
    {"name": "the compensation era and the voluntary-cut unwind", "start": "2024-04-22",
     "end": "2026-12-31",
     "regime": "Iraq files successive published compensation schedules against sustained "
               "over-production while the eight voluntary OPEC+ producers begin unwinding cuts "
               "on a published schedule; renewed sanctions enforcement tightens Iranian exports "
               "from 2025",
     "markers": ("2024-04-22 the first detailed Iraqi schedule", "2025-02-04 renewed "
                 "maximum-pressure enforcement", "2025-09-27 the partial Kurdish restart"),
     "why_it_matters": "the CURRENT regime, in which a scheduled supply addition meets an "
                       "administratively gated one; every cell this pack mints today sits in it",
     "status": "OPEN"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "IRAN AND SYRIA ARE UNDER COMPREHENSIVE SANCTIONS REGIMES, and this pack is "
                   "built entirely on PUBLIC material",
     "measured": "every source named for Iran and Syria is a published government page, a "
                 "published international-organisation report, a partner country's own customs "
                 "return, or public press",
     "consequence": "NOTHING IN THIS PACK TOUCHES ANY SANCTIONED ENTITY'S PRIVATE SYSTEMS, USES "
                    "ANY CREDENTIAL, OR BYPASSES ANY ACCESS CONTROL. Everything here is public: "
                    "OPEC's Monthly Oil Market Report, IEA and EIA public releases, OFAC's own "
                    "published designations and general licences, the US Federal Register, IMF "
                    "Article IV reports and published statistics, national central-bank and "
                    "statistics publications where they exist, published ICC and court records, "
                    "and public press. SANCTIONS CONSTRAIN TRANSACTIONS, NOT THE READING OF "
                    "PUBLISHED ADMINISTRATIVE ACTS AND STATISTICS -- and the desk executes only "
                    "broker symbols, never an Iraqi, Iranian, Jordanian, Lebanese or Syrian "
                    "instrument"},
    {"constraint": "none of the five currencies is quoted by this broker",
     "measured": "data/universe/universe.json holds no IQD, IRR, JOD, LBP or SYP symbol",
     "consequence": "every domestic mechanism terminates in crude, gas, the metals, the grain "
                    "and soft complex, the lira and shekel legs or the index legs; the five "
                    "currencies are INPUTS and never cells"},
    {"constraint": "three of the five currencies have two or more simultaneous rates",
     "measured": "IQD official and parallel; IRR official, NIMA and free; LBP official, Sayrafa, "
                 "banknote and lollar; SYP official and remittance",
     "consequence": "`parallel_premium` requires the pair to be named and returns UNMEASURED "
                    "otherwise; a cell that does not record which rate it used is not compiled"},
    {"constraint": "Syrian statistics largely stopped and the 2024-12-08 transition changed the "
                   "publishing institutions",
     "measured": "five source layers are DECLARED ABSENT for Syria with their substitutes named; "
                 "no IMF Article IV since before the war",
     "consequence": "OPECN-M and OPECN-N cite the MIRROR (Comtrade and the Turkish, Chinese, "
                    "Jordanian and Lebanese portals), FAO/GIEWS and WFP, or answer UNMEASURED"},
    {"constraint": "no international sell-side research on Iran lawfully exists",
     "measured": "the practitioner layer is DECLARED ABSENT for Iran with its substitute named",
     "consequence": "the Persian-language domestic analytical ground and the OPEC/IEA "
                    "secondary-source tables carry the practitioner information instead"},
    {"constraint": "the CBI auction page, the Lebanese official-rate page and the Tehran quote "
                   "pages all OVERWRITE IN PLACE",
     "measured": "none of the three keeps a history of its own",
     "consequence": "the point-in-time record exists only in the archive layer's crawls; a cell "
                    "compiled on an un-archived month is UNMEASURED rather than assumed"},
    {"constraint": "the Platts, Argus and fertiliser assessments forbid machine extraction",
     "measured": "registered with machine_use_allowed=false and never fetched",
     "consequence": "OPECN-A and OPECN-J are measured on the exchange-traded legs, the "
                    "ministry's own published volumes and the producers' own tonnages instead"},
    {"constraint": "the Islamic feasts are announcements and four different weekends run across "
                   "five neighbours",
     "measured": "LUNAR_HOLIDAYS is typed for 2024-2026 with every row naming all five "
                 "authorities; 2026 is PROJECTED throughout; `common_session_weekdays` derives "
                 "that only Monday, Tuesday and Wednesday are shared",
     "consequence": "a pooled 'regional session' study is a fiction, and any cell depending on a "
                    "2026 feast date carries the PROJECTED label until the sighting happens"},
    {"constraint": "the Strait of Hormuz bypass geography belongs to `gulf`",
     "measured": "`gulf` owns Duqm, Ras Markaz, Sohar and the within-country Mina al-Fahal "
                 "control",
     "consequence": "OPECN-O carries the RISK side only and USES the sibling's control rather "
                    "than duplicating it; duplicating would spend trial budget twice on one fact"},
)

INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "Amman Stock Exchange daily buy/sell by investor nationality and residency",
    "Central Bank of Iraq daily auction allocation and compliance rejection share",
    "Tehran Stock Exchange daily retail and institutional net flow",
    "Banque du Liban bi-monthly balance sheet: reserves, gold and currency in circulation",
    "Central Bank of Jordan monthly reserves and deposit dollarisation",
    "UN Comtrade and partner customs mirror trade for Syria, Iran and Iraq",
)
SERIES: dict[str, str] = {
    "OPECN_IQ_OSP": "SOMO:osp_basrah_differential",
    "OPECN_IQ_EXPORTS": "MOO:monthly_exports_bbl",
    "OPECN_IQ_REVENUE": "MOO:monthly_revenue_usd",
    "OPECN_IQ_AUCTION": "CBI:auction_allocation",
    "OPECN_IQ_PARALLEL": "MARKET:iqd_parallel_baghdad",
    "OPECN_KRG_EXPORTS": "MNR:krg_exports_bbl",
    "OPECN_IR_DIRECT": "OPEC:iran_direct_comm",
    "OPECN_IR_SECONDARY": "OPEC:iran_secondary_sources",
    "OPECN_IR_FREE": "MARKET:irr_free_rate",
    "OPECN_IR_COIN": "MARKET:bahar_azadi_premium",
    "OPECN_IR_SHAPARAK": "SHAPARAK:transaction_value",
    "OPECN_JO_POLICY": "CBJ:policy_rate",
    "OPECN_JO_RESERVES": "CBJ:fx_reserves",
    "OPECN_JO_POTASH": "DOS:potash_export_tonnage",
    "OPECN_LB_RESERVES": "BDL:fx_reserves",
    "OPECN_LB_OFFICIAL": "BDL:official_rate",
    "OPECN_LB_PARALLEL": "MARKET:lbp_banknote_rate",
    "OPECN_SY_MIRROR": "MIRROR:partner_reported_trade",
    "OPECN_WFP_BASKET": "WFP:food_basket_price",
    "OPECN_UNHCR_POP": "UNHCR:registered_population",
    "OPECN_OFAC": "OFAC:designation_events",
}

#: OTHER COUNTRY PACKS THIS ONE HAS A MEASURABLE INTERACTION WITH. This is how the desk stops
#: testing each country in isolation: a row here names WHICH other pack's observable must be
#: partialled out before this pack's claim is its own.
INTERACTIONS: tuple[dict[str, Any], ...] = (
    {"with": "gulf", "mechanism": "the Strait of Hormuz is the SHARED CONSTRAINT and the two "
                                  "packs own opposite halves of it: `gulf` owns the BYPASS "
                                  "geography (Duqm, Ras Markaz, Sohar, and Mina al-Fahal as the "
                                  "within-country control) and this pack owns the RISK side",
     "observable": "outside-strait loadings against inside-strait loadings around each incident",
     "targets": ("XBRUSD", "XNGUSD", "USDJPY"),
     "control": "USE the sibling's outside-strait control rather than duplicating it; an event "
                "that moves Gulf crude through the strait and NOT Omani loadings is a chokepoint "
                "event, and one that moves both is a price event"},
    {"with": "sa", "mechanism": "SAUDI ARAMCO'S OSP IS ANNOUNCED FIRST AND ANCHORS SOMO'S. The "
                                "Iraqi differential is set days later against the same "
                                "Oman/Dubai reference, and Saudi Arabia is also the swing "
                                "producer whose quota decisions bound Iraq's",
     "observable": "the Saudi OSP differential and its announcement date, and Saudi compliance",
     "targets": ("XBRUSD", "XTIUSD"),
     "control": "partial out the Saudi OSP day and the Saudi production decision before any "
                "Iraqi OSP or compliance claim is called Iraqi"},
    {"with": "tr", "mechanism": "TURKEY IS THE RESPONDENT IN THE ICC AWARD AND THE TRANSIT STATE "
                                "FOR THE SHUT PIPELINE; it is also the dominant trade partner "
                                "for Syria and a major one for Iraq and Iran, and the lira is "
                                "this pack's executable regional currency-crisis leg",
     "observable": "Ceyhan loadings, Turkish customs exports to Syria and Iraq, and Turkish "
                   "domestic policy events",
     "targets": ("USDTRY", "EURTRY", "GBPTRY", "XBRUSD"),
     "control": "EXCLUDE windows containing a Turkish domestic policy or crisis event, or a "
                "Levantine signal is measuring Ankara; GBPTRY against USDTRY separates a dollar "
                "move from a lira move"},
    {"with": "il", "mechanism": "the shekel is the other executable regional-risk leg, Israeli "
                                "gas supplies Jordan under a published agreement, and regional "
                                "security episodes that move the Hormuz and Levantine risk "
                                "premium frequently originate here",
     "observable": "dated regional security episodes and the Israeli gas export announcements",
     "targets": ("USDILS", "EURILS", "XNGUSD"),
     "control": "separate episodes that touched shipping or gas supply from those that did not; "
                "an episode that moves USDILS and not XNGUSD is not a supply event"},
    {"with": "dk", "mechanism": "THE DANISH PEG HAS NEVER FAILED AND THE LEBANESE ONE FAILED "
                                "COMPLETELY. `dk` is the out-of-region control that fixes the "
                                "far end of the peg-survival scale, with Jordan fixing the "
                                "in-region end; three pegs, two intact, one destroyed",
     "observable": "the Danish peg's band behaviour and reserve response over the identical "
                   "windows in which the Lebanese peg failed",
     "targets": ("EURUSD", "XAUUSD"),
     "control": "run every Lebanese peg-stress window against BOTH `dk` and Jordan; a stress "
                "measure that flags Denmark is measuring the global cycle and not peg solvency"},
    {"with": "eg", "mechanism": "EGYPT IS THE SOURCE OF THE ARAB GAS PIPELINE. When European gas "
                                "prices are high Egypt exports LNG instead of piping gas east, "
                                "so a Levantine power shortfall is frequently an Egyptian "
                                "arbitrage decision rather than a Levantine event",
     "observable": "Egyptian gas exports and LNG liftings against pipeline deliveries to Jordan",
     "targets": ("XNGUSD", "GER40"),
     "control": "condition on the European gas price regime before attributing a Jordanian or "
                "Lebanese supply interruption to the pipeline's politics"},
    {"with": "cn", "mechanism": "CHINESE INDEPENDENT REFINERS ARE THE RESIDUAL BUYER OF IRANIAN "
                                "CRUDE and Chinese customs is the mirror in which the volume is "
                                "visible; the declared-origin line is the standing example of "
                                "what a mirror reveals that a self-report does not",
     "observable": "Chinese customs crude imports by declared origin and the teapot run rate",
     "targets": ("USDCNH", "XBRUSD"),
     "control": "condition on the Chinese import cycle before an Iranian export claim is "
                "attributed to a sanctions act rather than to Chinese demand"},
    {"with": "ind", "mechanism": "INDIA WAS A MAJOR BUYER OF IRANIAN CRUDE UNTIL THE 2019-05-02 "
                                 "WAIVER EXPIRY and remains the largest single destination for "
                                 "Basrah grades and a major potash contract counterparty",
     "observable": "Indian customs crude imports by origin and the Indian potash contract "
                   "settlement",
     "targets": ("USDINR", "XBRUSD", "CORN"),
     "control": "partial out the Indian refining cycle and the Indian monsoon before a Basrah "
                "OSP or a Jordanian potash claim is called an Iraqi or Jordanian one"},
    {"with": "ma", "mechanism": "MOROCCO IS THE OTHER LARGE PHOSPHATE EXPORTER and the sibling "
                                "MENA pack shares the Hijri calendar, so both the fertiliser "
                                "route and the Eid seasonality are REGIONAL rather than "
                                "Jordanian or Levantine",
     "observable": "Moroccan phosphate exports and Morocco's own announced Eid dates",
     "targets": ("CORN", "WHEAT", "XAUUSD"),
     "control": "use Moroccan phosphate as the within-commodity control for the Jordanian claim "
                "and Morocco's announced dates as the out-of-region calendar control"},
)

# --------------------------------------------------------------------------- the testable cells
#: (mechanism_family, horizon) per domain -- what the gauntlet needs to file the cell.
DOMAIN_CELL_SPEC: dict[str, tuple[str, str]] = {
    "OPECN-A": ("administered_price", "0-10 sessions"),
    "OPECN-B": ("supply_shock", "0-20 sessions"),
    "OPECN-C": ("quota_compliance", "1-2 quarters"),
    "OPECN-D": ("parallel_premium", "0-10 sessions"),
    "OPECN-E": ("policy_event", "1-4 quarters"),
    "OPECN-F": ("series_divergence", "0-20 sessions"),
    "OPECN-G": ("inflation_expectation", "1-4 weeks"),
    "OPECN-H": ("seasonality", "2-8 weeks"),
    "OPECN-I": ("peg_control", "0-20 sessions"),
    "OPECN-J": ("input_cost", "1-2 quarters"),
    "OPECN-K": ("peg_failure", "0-20 sessions"),
    "OPECN-L": ("import_demand", "0-10 sessions"),
    "OPECN-M": ("mirror_statistics", "1-2 quarters"),
    "OPECN-N": ("regime_boundary", "1-2 quarters"),
    "OPECN-O": ("chokepoint_risk", "0-10 sessions"),
    "OPECN-P": ("physical_flow", "2-8 weeks"),
    "OPECN-Q": ("remittance_cycle", "2-4 quarters"),
    "OPECN-R": ("fiscal_shock", "1-2 quarters"),
}


def cells() -> tuple[dict[str, Any], ...]:
    """Every testable cell this pack mints: domain x its own instruments x its own conditions.

    Each row is what the gauntlet needs to compile one test -- the symbol, the condition that
    gates it, the mechanism family, the horizon, and the negative control the domain declared,
    so a cell can never travel without one. A cell whose condition this pack's own data plane
    cannot evaluate is not minted, which is why the count is in the low hundreds.
    """
    out: list[dict[str, Any]] = []
    for dom in DOMAINS:
        did = str(dom["id"])
        family, horizon = DOMAIN_CELL_SPEC.get(did, ("residual", "0-10 sessions"))
        controls = tuple(dom["controls"])
        for sym in dom["instruments"]:
            for i, cond in enumerate(dom["conditions"]):
                out.append({
                    "cell_id": f"{CODE.lower()}:{did}:{sym}:c{i}",
                    "domain": did, "symbol": str(sym), "condition": str(cond),
                    "mechanism_family": family, "horizon": horizon,
                    "control": str(controls[i % len(controls)]),
                    "jurisdiction": str(dom.get("jurisdiction") or "shared"),
                    "why": str(dom["title"]),
                })
    return tuple(out)


# --------------------------------------------------------------------------- the pack's miners
def _emit(ctx: Any, kind: str, text: str) -> bool:
    """Note one line through the department context when there is one. A miner with no context
    is a DRY RUN and says so in its report rather than pretending to have recorded anything."""
    note = getattr(ctx, "note", None)
    if callable(note):
        note(kind, text)
        return True
    return False


def mine_osp_clock(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The SOMO announcement clock and the published compensation schedules (OPECN-A, OPECN-C)."""
    rows = [{"announced": d.isoformat(), "window": w, "pledged_kbd": kbd, "status": st}
            for d, w, kbd, st in IRAQ_COMPENSATION]
    emitted = sum(1 for r in rows
                  if _emit(ctx, "opecn_compensation",
                           f"{r['announced']}: {r['pledged_kbd']} kb/d over {r['window']} "
                           f"[{r['status']}]"))
    return {"miner": "opecn_osp_clock", "rows": rows, "emitted": emitted,
            "unmeasured": ["the SOMO OSP differential series is named in DATASETS and is not "
                           "carried on this tree; the Saudi OSP announcement date, which is the "
                           "control, is likewise named and not carried"],
            "targets": ("XBRUSD", "XTIUSD", "USDINR")}


def mine_pipeline_state(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The dated Kurdistan-Ceyhan state transitions (OPECN-B)."""
    rows = [kurdistan_pipeline_state(d) for d, *_rest in KURDISTAN_PIPELINE]
    emitted = sum(1 for r in rows
                  if _emit(ctx, "opecn_pipeline",
                           f"{r['since']}: {r['state']} at {r['kbd']} kb/d [{r['evidence']}]"))
    return {"miner": "opecn_pipeline_state", "rows": rows, "emitted": emitted,
            "unmeasured": ["Iraqi FEDERAL export volumes are the control and are named in "
                           "DATASETS, not carried here; without them a routing event reads as a "
                           "supply event"],
            "targets": ("XBRUSD", "XTIUSD", "USDTRY")}


def mine_rate_lattice(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The five currencies' regimes and the Lebanese official ladder (OPECN-D/G/K/N)."""
    rows = [{"currency": c, "jurisdiction": str(v["jurisdiction"]), "regime": str(v["regime"]),
             "official": v["official"], "since": str(v["since"])}
            for c, v in CURRENCIES.items()]
    ladder = [lbp_official_rate(d) for d, *_rest in LBP_OFFICIAL_LADDER]
    emitted = sum(1 for r in rows
                  if _emit(ctx, "opecn_rate",
                           f"{r['currency']} ({r['jurisdiction']}) {r['regime']} "
                           f"official={r['official']} since {r['since']}"))
    return {"miner": "opecn_rate_lattice", "rows": rows, "ladder": ladder, "emitted": emitted,
            "unmeasured": ["the PARALLEL series for IQD, IRR, LBP and SYP are not carried on "
                           "this tree, so the premium is a TRANSMISSION hypothesis and not a "
                           "compiled cell until a parallel series is carried"],
            "targets": ("XAUUSD", "USDTRY", "EURTRY")}


def mine_sanctions_clock(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The dated, PUBLISHED US administrative acts as an event clock (OPECN-E, OPECN-F)."""
    rows = [{"date": d.isoformat(), "act": act, "direction": sign}
            for d, act, sign in IRAN_SANCTIONS_ACTS]
    emitted = sum(1 for r in rows
                  if _emit(ctx, "opecn_sanctions",
                           f"{r['date']} [{r['direction']}]: {r['act']}"))
    return {"miner": "opecn_sanctions_clock", "rows": rows, "emitted": emitted,
            "unmeasured": ["the two OPEC production tables are named in DATASETS and are not "
                           "carried here; the GAP between them is the observable and is "
                           "UNMEASURED on this tree"],
            "targets": ("XBRUSD", "XTIUSD", "USDCNH")}


def mine_calendar(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The derived Iranian year, both Easter computi and the four weekend regimes (OPECN-G/L/Q)."""
    rows: list[dict[str, Any]] = []
    for year in sorted(HOLIDAYS_RULE["years"]):
        start = nowruz(year)
        rows.append({"year": year, "nowruz": start.isoformat(),
                     "solar_hijri_year": solar_hijri_year(start),
                     "sizdah_bedar": (start + timedelta(days=12)).isoformat(),
                     "western_easter": western_easter(year).isoformat(),
                     "orthodox_easter": orthodox_easter(year).isoformat(),
                     "easter_gap_days": (orthodox_easter(year) - western_easter(year)).days,
                     "closures": len(market_holidays(year))})
    emitted = sum(1 for r in rows
                  if _emit(ctx, "opecn_calendar",
                           f"{r['year']}: Nowruz {r['nowruz']} (SH {r['solar_hijri_year']}), "
                           f"Easter gap {r['easter_gap_days']}d, "
                           f"{r['closures']} session-costing closures"))
    return {"miner": "opecn_calendar", "rows": rows, "emitted": emitted,
            "weekends": {cc: WEEKENDS[cc] for cc in JURISDICTIONS},
            "common_session_weekdays": common_session_weekdays(),
            "unmeasured": ["2026 is PROJECTED for every lunar row: no 2026 sighting has "
                           "happened, so a cell compiled on a 2026 feast date carries that label"],
            "targets": ("XAUUSD", "WHEAT", "XBRUSD")}


def mine_mirror_substitutes(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The MEASURED REFUSALS: every declared layer absence with its named substitute (M, N)."""
    rows = list(declared_absences())
    emitted = sum(1 for r in rows
                  if _emit(ctx, "opecn_absence",
                           f"{r['jurisdiction']}/{r['layer']} ABSENT -- substitute: "
                           f"{r['substitute'][:90]}"))
    return {"miner": "opecn_mirror_substitutes", "rows": rows, "emitted": emitted,
            "no_lawful_ground": [row["what"] for row in NO_LAWFUL_GROUND],
            "unmeasured": ["UN Comtrade and the three partner customs portals are the named "
                           "substitutes and are not carried on this tree; a Syrian or Iranian "
                           "cell cites the mirror or answers UNMEASURED"],
            "targets": ("WHEAT", "COTTON", "USDCNH")}


def mine_transmission_seeds(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The pack's own transmission map, emitted as HYPOTHESIS rows."""
    rows = [{"id": str(e["id"]), "target": str(e["target"]), "targets": tuple(e["targets"]),
             "evidence": str(e["evidence"]), "sign": str(e["sign"])}
            for e in TRANSMISSION_EDGES_SEED]
    emitted = sum(1 for r in rows
                  if _emit(ctx, "opecn_seed",
                           f"{r['id']} -> {', '.join(r['targets'])} [{r['evidence']}]"))
    return {"miner": "opecn_transmission_seeds", "rows": rows, "emitted": emitted,
            "unmeasured": [], "targets": tuple(sorted({t for e in TRANSMISSION_EDGES_SEED
                                                       for t in e["targets"]}))}


MINERS: dict[str, Any] = {
    "mine_osp_clock": mine_osp_clock,
    "mine_pipeline_state": mine_pipeline_state,
    "mine_rate_lattice": mine_rate_lattice,
    "mine_sanctions_clock": mine_sanctions_clock,
    "mine_calendar": mine_calendar,
    "mine_mirror_substitutes": mine_mirror_substitutes,
    "mine_transmission_seeds": mine_transmission_seeds,
}


def mine(ctx: Any = None) -> dict[str, Any]:
    """THE DEPARTMENT ENTRY. Pure python, no network, no LLM, no heavy import.

    It runs the pack's own miners over the pack's own data, emits through the department context
    when one is given, and returns a plain report when one is not. `cells_emitted` is the number
    that matters: how many testable cells this pack is offering the one gauntlet, COUNTED from
    `cells()` rather than claimed.
    """
    reports = [fn(None, ctx) for fn in MINERS.values()]
    rows: list[dict[str, Any]] = []
    unmeasured: list[str] = []
    emitted = 0
    for rep in reports:
        emitted += int(rep.get("emitted") or 0)
        unmeasured.extend(str(u) for u in rep.get("unmeasured") or ())
        rows.append({"miner": rep["miner"], "n_rows": len(rep.get("rows") or ()),
                     "targets": tuple(rep.get("targets") or ())})
    minted = cells()
    return {"code": CODE.lower(), "jurisdictions": JURISDICTIONS,
            "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "emitted": emitted, "rows": rows, "unmeasured": unmeasured,
            "cells_emitted": len(minted),
            "cells_by_domain": {d["id"]: sum(1 for c in minted if c["domain"] == d["id"])
                                for d in DOMAINS},
            "datasets": len(DATASETS), "actors": len(ACTORS), "domains": len(DOMAINS),
            "edges": len(TRANSMISSION_EDGES_SEED), "interactions": len(INTERACTIONS),
            "declared_absences": len(declared_absences()),
            "dry_run": not hasattr(ctx, "note"),
            "note": "UNWIRED IS A DEFECT (III.16): this department returns an artifact on every "
                    "call and names what it could not measure rather than reporting 'built'"}


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
        "jurisdictions": JURISDICTIONS, "currencies": CURRENCIES,
        "executable_instruments": EXECUTABLE_INSTRUMENTS, "central_bank": CENTRAL_BANK,
        "central_banks": CENTRAL_BANKS,
        "fixing_conventions": FIXING_CONVENTIONS,
        "settlement_conventions": SETTLEMENT_CONVENTIONS, "exchanges": EXCHANGES,
        "release_classes": RELEASE_CLASSES, "session_windows": SESSION_WINDOWS,
        "holidays_rule": HOLIDAYS_RULE, "fiscal_year_end": FISCAL_YEAR_END,
        "fiscal_year_ends": FISCAL_YEAR_ENDS,
        "positioning_sources": POSITIONING_SOURCES, "native_languages": NATIVE_LANGUAGES,
        "terminology": TERMINOLOGY, "source_classes": SOURCE_CLASSES,
        "source_layers": SOURCE_LAYERS, "layer_absences": LAYER_ABSENCES,
        "layer_terms": layer_terms(), "source_layer_coverage": source_layer_coverage(),
        "declared_absences": declared_absences(),
        "query_territories": QUERY_TERRITORIES, "no_lawful_ground": NO_LAWFUL_GROUND,
        "datasets": DATASETS, "actors": ACTORS, "domains": DOMAINS,
        "custom_miners": CUSTOM_MINERS, "miner_domains": MINER_DOMAINS,
        "transmission_edges_seed": TRANSMISSION_EDGES_SEED, "policy_eras": POLICY_ERAS,
        "transmission_targets": TRANSMISSION_TARGETS, "access_constraints": ACCESS_CONSTRAINTS,
        "region_desk": REGION_DESK, "forest": FOREST, "cot_currency": COT_CURRENCY,
        "export_economy": EXPORT_ECONOMY, "retail_leverage_regime": RETAIL_LEVERAGE_REGIME,
        "retail_leverage_by_jurisdiction": RETAIL_LEVERAGE_BY_JURISDICTION,
        "institutional_flow_sources": INSTITUTIONAL_FLOW_SOURCES, "series": SERIES,
        "mission": MISSION, "interactions": INTERACTIONS, "cells": cells(),
        "lbp_official_ladder": LBP_OFFICIAL_LADDER,
        "lebanon_collapse_markers": LEBANON_COLLAPSE_MARKERS,
        "kurdistan_pipeline": KURDISTAN_PIPELINE, "iraq_compensation": IRAQ_COMPENSATION,
        "iran_sanctions_acts": IRAN_SANCTIONS_ACTS, "weekends": WEEKENDS,
        "ramadan_windows": RAMADAN_WINDOWS, "sighting_authorities": SIGHTING_AUTHORITIES,
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
                      f"machine_use_allowed={sc['machine_use_allowed']} | "
                      f"jurisdictions={','.join(sc.get('jurisdictions') or ()) or 'shared'} | "
                      f"{sc['notes']}")}


def _absent_row(sc: Mapping[str, Any]) -> dict[str, Any]:
    """A declared absence in the framework's own SourceRow shape, so `pack_depth` counts the
    layer as MAPPED rather than unmapped -- a named absence IS coverage of the question."""
    return {"id": sc["id"], "layer": sc["layer"], "label": sc["label"], "roots": (),
            "languages": (), "licence": "n/a", "verified": False,
            "absent_reason": str(sc.get("reason") or sc.get("notes") or ""),
            "query_terms": (), "notes": str(sc["notes"])}


def _holiday_rule_row() -> dict[str, Any]:
    """The framework's HolidayRule shape: every session-costing closure the rule produces for
    2024-2026, the fixed month-days it derives them from, and the majority weekend."""
    dates = sorted({d.isoformat() for y in HOLIDAYS_RULE["years"] for d in market_holidays(y)})
    fixed = sorted({f"{m:02d}-{d:02d}"
                    for rows in FIXED_NATIONAL.values() for m, d, _n in rows})
    return {"dates": tuple(dates), "fixed_md": tuple(fixed),
            "weekly_closed": WEEKEND_WEEKDAYS, "notes": str(HOLIDAYS_RULE["authority"])}


def lab_kwargs() -> dict[str, Any]:
    """The keyword set `country_lab.CountryPack` is built from, in the shapes its coercion reads
    best: sources as rows AND as tagged lines, positioning and miners as strings, the holiday
    rule as dates, absent layers as a mapping."""
    data = as_dict()
    real = [s for s in SOURCE_CLASSES if not str(s["id"]).startswith("absent_")]
    gone = [s for s in SOURCE_CLASSES if str(s["id"]).startswith("absent_")]
    data.update({
        "code": CODE.lower(),
        "positioning_sources": tuple(str(p["name"]) for p in POSITIONING_SOURCES),
        "custom_miners": tuple(str(m["entry"]) for m in CUSTOM_MINERS),
        "source_classes": tuple(_source_line(s) for s in real),
        "sources": tuple([_source_row(s) for s in real] + [_absent_row(s) for s in gone]),
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
