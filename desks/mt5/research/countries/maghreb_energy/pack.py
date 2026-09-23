"""THE MAGHREB ENERGY AND MINERALS PLANE -- Algeria, Libya, Tunisia and Mauritania.

WHY ONE PACK AND NOT FOUR, AND WHY IT IS NOT A FOOTNOTE TO `ma`. The desk already holds Morocco
(`ma`): a basket peg, the world's phosphate rock, a cereal import on a decree clock. This pack is
the rest of the Maghreb, and it is a DIFFERENT MACHINE -- Morocco imports energy and this pack
EXPORTS it. Four things belong here and to no other pack on this desk:

  1. ALGERIA IS THE EUROPEAN UNION'S THIRD-LARGEST PIPELINE GAS SUPPLIER AND BECAME ITALY'S
     LARGEST AFTER 2022, AND THE FLOW IS PUBLISHED DAILY. Sonatrach exports through the
     Transmed / Enrico Mattei line to Sicily and through Medgaz to Almeria, and both entry
     volumes appear in a European TSO's own transparency data -- Transmed at Mazara del Vallo in
     Snam's daily entry-point table, Medgaz in Enagas's. A PHYSICAL, DAILY, OPEN series carrying
     roughly a tenth of European gas supply is the rarest object a gas desk can hold, and the
     dated events around it are published too: the Maghreb-Europe pipeline through Morocco was
     SHUT on 2021-10-31 in the Algeria-Morocco rupture, the Italy-Sonatrach supply agreements
     were signed in April and July 2022, and the Spain-Algeria diplomatic rupture followed in
     June 2022. Algeria's own domestic demand -- subsidised, and peaking in summer on air
     conditioning -- is the constraint on the export, which makes the seasonal residual a
     physically causal series rather than a seasonal dummy.

  2. LIBYA IS THE MOST VOLATILE OPEC PRODUCER ON EARTH AND ITS OUTAGES ARE DATED, NAMED AND
     PUBLISHED. The National Oil Corporation declares force majeure BY TERMINAL -- Es Sider, Ras
     Lanuf, Zueitina, Brega, Hariga -- and publishes production; Sharara and El Feel have been
     shut and restarted repeatedly on political triggers; the 2020-01-18 blockade removed about
     1.1 mb/d for eight months; the August-October 2024 central-bank governorship dispute took
     roughly 700 kb/d offline for weeks. That is about one per cent of world supply switching on
     and off on published, dated, NON-ECONOMIC triggers, which is as close to an instrumental
     variable for an oil supply shock as this market offers. MGB-E is a domain of its own with
     per-terminal cells for exactly that reason.

  3. TUNISIA IS THREE MECHANISMS IN ONE STATE. It is the TRANSIT COUNTRY for Algerian gas to
     Italy and takes an IN-KIND ROYALTY on the Transmed volume, so a Tunisian transit event is an
     Italian supply event. It is a top-three world OLIVE OIL producer on a dated, weather-driven
     campaign published by ONAGRI. And it is one of the largest PHOSPHATE producers through the
     Compagnie des Phosphates de Gafsa, whose output has been halted repeatedly by dated,
     published labour actions -- feeding the fertiliser cost that sets northern-hemisphere grain
     acreage. On top of that it is a live sovereign-stress case with an IMF programme agreed at
     staff level and publicly refused at the political level, on dated decision points.

  4. MAURITANIA IS AN IRON-ORE AND LNG STATE WITH AN ATLANTIC FISHERY. SNIM's ore runs to
     Nouadhibou on the longest train in the world and the tonnage is published monthly; Greater
     Tortue Ahmeyim -- SHARED WITH SENEGAL, so this pack and `west_africa` are one physical
     system -- is a dated LNG capacity ramp with first gas in 2025; and the EU and Chinese
     fleets fish Mauritanian water under published agreements. Iron ore routes into the China
     complex and the fish into the same, each with its control named.

WHAT IS EXECUTABLE AND WHAT IS NOT. THE DINAR (DZD), THE LIBYAN DINAR (LYD), THE TUNISIAN DINAR
(TND) AND THE OUGUIYA (MRU) ARE ALL ABSENT from `data/universe/universe.json`, and so are the
European gas hubs this pack is really about: TTF, PSV and PVB are not Fusion symbols. Every one
is named in TRANSMISSION_TARGETS with its regime and the broker symbols its economics reach, so
an absent instrument mints a transmission hypothesis and never a cell that can never be filled
(L1.49).

HENRY HUB IS A CONTROL AND NOT A PROXY, and this pack says so on the record. European and US gas
decoupled by an order of magnitude in 2022; a study that swapped one benchmark for the other
would have measured the transatlantic LNG arbitrage and reported it as a European supply shock.
XNGUSD is the executable leg the desk has, the TSOs' published PHYSICAL FLOWS are the European
observable, and the US benchmark enters every gas domain below as the NEGATIVE CONTROL. (The `ea`
pack makes the same point about TTF for its own ground; the discipline is borrowed, the pack is
not duplicated.)

THE TWO-LANE ORDER (2026-09-06). Sonatrach, the NOC, CPG, SNIM, ETAP, Sonelgaz, BP and Kosmos are
the names this ground talks about and every one of them is an EVENT-lane instrument or an unlisted
state company. They appear here as ACTORS and as TERMINOLOGY so an Arabic- and French-language
miner recognises the words. Not one is a symbol in any instrument tuple in this file.

NO CRYPTO-EXCHANGE GROUND IS HUNTED (mandate 2026-08-18): no venue, order book or exchange feed
is named as a source anywhere below. The parallel-currency ground in this pack is PRESS AND
TRACKER REPORTING of a cash market, which is a different object entirely.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "maghreb_energy"
NAME = "The Maghreb energy and minerals plane (Algeria, Libya, Tunisia, Mauritania)"
REGION_COMMAND = "mea"             # the framework's command; the forest is mena
REGION_DESK = "MENA"
FOREST = "mena"
CURRENCY = "DZD"                   # the pack's nominal currency; the other three are below
#: THE FOUR ISO-2 CODES THIS PACK ANSWERS FOR. `check_regional_parity.jurisdictions_of` reads
#: this tuple and nothing else: a multi-country pack that declares nothing is credited with ONE
#: country, which would leave three of the parity fence's named gaps unanswered while the work
#: sat on disk.
JURISDICTIONS: tuple[str, ...] = ("dz", "ly", "tn", "mr")

#: FOUR CURRENCIES AND FOUR DIFFERENT REGIMES. Not one of them is quoted by this broker, and the
#: differences between them are the point: a pooled "Maghreb FX" study is measuring a managed
#: float with a large parallel premium, a dinar that was unified once and devalued again, a
#: managed rate behind capital controls, and a currency that was REDENOMINATED 10:1 in 2018.
CURRENCIES: dict[str, dict[str, Any]] = {
    "DZD": {"jurisdiction": "dz", "name": "Algerian dinar", "regime": "managed_float",
            "authority": "Bank of Algeria -- بنك الجزائر / Banque d'Algerie",
            "since": "1994-10-01",
            "parallel_market": True,
            "fact": "a MANAGED FLOAT set in a daily interbank fixing session the central bank "
                    "dominates, with a LARGE AND PUBLICLY REPORTED PARALLEL PREMIUM: the cash "
                    "rate quoted on the Square Port Said in Algiers is the second price of the "
                    "dinar, it is reported only by the press and by private trackers, and its "
                    "spread to the official rate is the capital-control stress state MGB-D "
                    "conditions on. The premium is an OBSERVABLE with a credibility label, "
                    "never an official series"},
    "LYD": {"jurisdiction": "ly", "name": "Libyan dinar", "regime": "peg",
            "authority": "Central Bank of Libya -- مصرف ليبيا المركزي",
            "since": "2020-12-16",
            "parallel_market": True,
            "fact": "TWO DATED STEPS AND A SPLIT INSTITUTION. The CBL UNIFIED the exchange rate "
                    "on 2020-12-16 (effective 2021-01-03) at 4.48 LYD per USD, ending years in "
                    "which the official and parallel rates were different currencies in "
                    "practice; it DEVALUED again in 2024 to about 5.5677. The bank itself was "
                    "split between Tripoli and al-Bayda from 2014 until the 2023 reunification, "
                    "and the two halves at times published different numbers for the same "
                    "aggregate -- which is why no Libyan monetary series is pooled across 2014 "
                    "to 2023 in this pack"},
    "TND": {"jurisdiction": "tn", "name": "Tunisian dinar", "regime": "managed_float",
            "authority": "Banque Centrale de Tunisie -- البنك المركزي التونسي",
            "since": "2016-01-01",
            "parallel_market": False,
            "fact": "a managed rate behind CAPITAL CONTROLS: the dinar is not convertible for "
                    "capital account purposes, residents may not hold foreign currency freely, "
                    "and the BCT publishes a daily reference rate. There is a cash margin but "
                    "no large organised parallel market of the Algerian kind, which makes "
                    "Tunisia the WITHIN-REGION CONTROL for every parallel-premium claim this "
                    "pack makes about Algeria and Libya"},
    "MRU": {"jurisdiction": "mr", "name": "Mauritanian ouguiya", "regime": "managed_float",
            "authority": "Banque Centrale de Mauritanie -- البنك المركزي الموريتاني",
            "since": "2018-01-01",
            "parallel_market": True,
            "fact": "REDENOMINATED 10:1 ON 2018-01-01: one MRU replaced ten MRO. A level series "
                    "spliced across that date is wrong BY A FACTOR OF TEN and a ratio series "
                    "spliced across it is silently right, which is the most dangerous kind of "
                    "break there is. `mru_redenominate` is the pack's own conversion and the "
                    "reason it exists"},
}

FISCAL_YEAR_END = "12-31"
#: All four run the calendar year. The DIFFERENCE that matters is not the fiscal year but the
#: CAMPAIGN year: the Tunisian olive campaign runs 1 November to 31 October, so a Tunisian
#: agricultural claim filed on a calendar year is cut through the middle of its own harvest.
FISCAL_YEAR_ENDS: dict[str, str] = {"dz": "12-31", "ly": "12-31", "tn": "12-31", "mr": "12-31"}

#: ARABIC AND FRENCH, AND THE PACK MEANS BOTH. Arabic is the language of the law, the gazettes
#: and the press in all four states. FRENCH is the language of the FINANCIAL AND TECHNICAL
#: ADMINISTRATION in Algeria, Tunisia and Mauritania -- the central banks' bulletins, the
#: customs tariff, the statistics offices' tables, the engineering documentation of the pipelines
#: and the mines are French-first, and frequently French-only. A pack that crawls only Arabic
#: here reads the press and misses the balance sheet; one that crawls only French reads the
#: balance sheet and misses the gazette, the sighting announcement and the street. TAMAZIGHT is
#: an OFFICIAL LANGUAGE OF ALGERIA (constitutional revision of 2016) written in Tifinagh, and
#: Mauritania's national languages are Hassaniya Arabic, Pulaar, Soninke and Wolof -- the layers
#: that reach ordinary economic behaviour in either country are not written in French at all.
NATIVE_LANGUAGES: tuple[str, ...] = ("ar", "fr", "ber", "mey", "ff", "snk", "wo", "en")
LANGUAGE_NOTES: dict[str, str] = {
    "ar": "the law, the gazettes (JORADP, IORT), the press and the religious calendar in all four",
    "fr": "the financial and technical administration of dz, tn and mr: central-bank bulletins, "
          "the customs tariff, the statistics tables, the pipeline and mining documentation",
    "ber": "Tamazight, OFFICIAL IN ALGERIA SINCE THE 2016 CONSTITUTIONAL REVISION, written in "
           "Tifinagh; Kabyle is the largest variety and Yennayer became an official Algerian "
           "public holiday in 2018 -- a DATED ADDITION TO A MARKET CALENDAR",
    "mey": "Hassaniya Arabic, the spoken language of Mauritania and the western Sahara",
    "ff": "Pulaar, a Mauritanian national language of the Senegal river valley",
    "snk": "Soninke, a Mauritanian national language",
    "wo": "Wolof, a Mauritanian national language and the link to the Senegalese side of the "
          "shared GTA gas field (`west_africa`)",
    "en": "the language of the multilateral record: IMF Article IV, the UN Panel of Experts on "
          "Libya, OPEC's MOMR, the IEA and EIA releases and the LNG trade press",
}

COT_CURRENCY = ""                  # no CFTC contract exists for DZD, LYD, TND or MRU
EXPORT_ECONOMY = "energy_exporter"
RETAIL_LEVERAGE_REGIME = "restricted"
#: Per jurisdiction, because the four are not one regime. None of the four licenses retail margin
#: FX; Algeria and Tunisia forbid a resident from funding an offshore margin account under
#: exchange control, Libya has no functioning regulator of the kind, and Mauritania has no
#: securities market at all.
RETAIL_LEVERAGE_BY_JURISDICTION: dict[str, str] = {
    "dz": "restricted", "ly": "restricted", "tn": "restricted", "mr": "restricted"}

MISSION = ("mine the Maghreb as the EUROPEAN GAS AND MINERALS SUPPLY PLANE it is: Algeria's "
           "Transmed and Medgaz flows as a daily published series and the 2021 Maghreb-Europe "
           "closure as the dated event that ended the third route; Libya's per-terminal force "
           "majeure as an instrument for an oil supply shock; Tunisia as the transit state, the "
           "olive campaign and the Gafsa phosphate strike; Mauritania's SNIM iron ore and the "
           "Greater Tortue Ahmeyim ramp it shares with Senegal -- with four currencies in four "
           "regimes, none of them quoted, all of them routed")

#: The instruments this pack may compile a cell against. Every one is in the broker registry and
#: none is a single-name equity. All four local currencies and all three European gas hubs are
#: absent (see TRANSMISSION_TARGETS).
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "XNGUSD",                                          # the gas leg; Henry Hub is the CONTROL
    "XBRUSD", "XTIUSD",                                # Libyan and Algerian crude, the OPEC clock
    "XAUUSD",                                          # reserves, the cash hedge, the Eid season
    "XALUSD", "XCUUSD",                                # the industrial-metal leg of iron and ore
    "WHEAT", "CORN", "SOYBEAN",                        # the fertiliser input and the import bill
    "SUGAR", "COTTON",                                 # the subsidised food basket and the fibre
    "EURUSD",                                          # the euro is the invoice and the frontier
    "GER40", "FRA40", "NETH25", "EUSTX50", "E35",      # European energy cost, by country
    "UK100",                                           # the European energy complex's other tape
    "USDTRY", "EURTRY",                                # the Mediterranean frontier-stress beta
    "USDZAR",                                          # the African commodity-risk beta
    "USDCNH",                                          # the buyer of the iron ore and the fish
)

#: EVERY LOCAL AND EVERY EUROPEAN-HUB PRICE THIS PACK IS ABOUT, NAMED ABSENT WITH WHAT CARRIES
#: IT. `proxies` must all resolve in the broker registry -- a transmission target with an
#: unquotable carrier is an absence dressed as a route.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "DZD official (the Bank of Algeria daily interbank fixing)",
     "venue": "Bank of Algeria interbank foreign-exchange market",
     "why": "the official price of the dinar and the one the trade account is settled at; the "
            "currency every Algerian mechanism here is about, and absent from the broker",
     "regime": "managed float since 1994; a daily fixing session the central bank dominates",
     "proxies": ("EURUSD", "XBRUSD", "XNGUSD")},
    {"name": "DZD parallel (the Square Port Said cash rate in Algiers)",
     "venue": "the informal cash market; reported by the press and by private trackers",
     "why": "THE SECOND PRICE OF THE DINAR. Its spread to the official fixing is the "
            "capital-control stress state MGB-D conditions on, and it is the only public read on "
            "Algerian import demand for hard currency",
     "regime": "unofficial, tolerated, never published by any authority; REPORTED ground with a "
               "credibility label, never an official series",
     "proxies": ("EURUSD", "XAUUSD", "USDTRY")},
    {"name": "LYD official (the Central Bank of Libya rate)",
     "venue": "Central Bank of Libya",
     "why": "unified on 2020-12-16 at 4.48 and devalued again in 2024; the two steps are the "
            "only dated Libyan monetary events with a published number attached",
     "regime": "peg to a USD rate set by the CBL board; two boards from 2014 to 2023",
     "proxies": ("XBRUSD", "XAUUSD", "USDTRY")},
    {"name": "LYD parallel (the Tripoli and Benghazi cash rate)",
     "venue": "the informal cash market and the letter-of-credit queue",
     "why": "before the 2020 unification the parallel rate was three to four times the official "
            "one, so an 'exchange rate' series for Libya before 2021 is two different prices "
            "with one name",
     "regime": "unofficial; the spread narrowed sharply at unification and widened again in 2024",
     "proxies": ("XAUUSD", "XBRUSD", "USDTRY")},
    {"name": "TND (the Banque Centrale de Tunisie daily reference rate)",
     "venue": "Banque Centrale de Tunisie",
     "why": "a managed rate behind capital controls; the dinar is not capital-account "
            "convertible, which makes Tunisia the within-region CONTROL for the two parallel "
            "premiums this pack measures",
     "regime": "managed float since 2016 with capital controls; a published daily reference rate",
     "proxies": ("EURUSD", "EURTRY", "E35")},
    {"name": "MRU (the Banque Centrale de Mauritanie rate, redenominated 2018-01-01)",
     "venue": "Banque Centrale de Mauritanie FX auctions",
     "why": "a managed rate on a mining-and-fish export base; the 10:1 REDENOMINATION of "
            "2018-01-01 is a series break that silently multiplies a level by ten",
     "regime": "managed float; MRU replaced MRO at 1:10 on 2018-01-01",
     "proxies": ("USDCNH", "EURUSD", "XAUUSD")},
    {"name": "TTF (Dutch Title Transfer Facility) -- the European gas benchmark",
     "venue": "the Dutch virtual trading point and the exchanges that clear it",
     "why": "THE PRICE THIS PACK'S GAS MECHANISMS ACTUALLY MOVE, and it is not a Fusion symbol. "
            "The executable leg is XNGUSD and the European observable is the TSOs' PUBLISHED "
            "PHYSICAL FLOW; HENRY HUB IS THE CONTROL AND NEVER THE PROXY, because the two "
            "benchmarks decoupled by an order of magnitude in 2022 and a study that substituted "
            "one for the other measured the LNG arbitrage and called it a European shock",
     "regime": "n/a (a traded hub)",
     "proxies": ("XNGUSD", "NETH25", "EUSTX50", "EURUSD")},
    {"name": "PSV (Punto di Scambio Virtuale) -- the Italian gas hub",
     "venue": "the Italian virtual trading point; Snam is the TSO",
     "why": "Algeria became ITALY'S LARGEST PIPELINE SUPPLIER after 2022 and the Transmed entry "
            "at Mazara del Vallo is where that arrives; the PSV-TTF spread is the Italian "
            "supply-security premium and neither leg is quoted here",
     "regime": "n/a (a traded hub)",
     "proxies": ("XNGUSD", "EUSTX50", "EURUSD")},
    {"name": "PVB (Punto Virtual de Balance) -- the Spanish gas hub",
     "venue": "the Spanish virtual trading point; Enagas is the TSO",
     "why": "Medgaz lands at Almeria and the Maghreb-Europe line into Tarifa was SHUT on "
            "2021-10-31, so Spain's Algerian supply became single-route; the PVB-TTF spread "
            "carries the Iberian exception and neither leg is quoted here",
     "regime": "n/a (a traded hub)",
     "proxies": ("XNGUSD", "E35", "EURUSD")},
    {"name": "Henry Hub (the US benchmark) -- REGISTERED AS A CONTROL, NOT A PROXY",
     "venue": "the US physical and futures market",
     "why": "named here so that no cell in this pack can quietly substitute it for a European "
            "price: it is the NEGATIVE CONTROL that separates a Maghreb supply event from a "
            "global gas move, and a European claim that also appears in the US benchmark is a "
            "global claim wearing an Algerian hat",
     "regime": "n/a (the control leg)",
     "proxies": ("XNGUSD",)},
    {"name": "Saharan Blend and the Libyan crude grades (Es Sider, Sharara, Amna, Bouri)",
     "venue": "the physical differentials to Dated Brent",
     "why": "the grades that actually move when a terminal declares force majeure; the "
            "differentials are assessed by price reporting agencies and are not quoted here, so "
            "the executable leg is the crude benchmark and the observable is COUNTED PRODUCTION",
     "regime": "n/a (physical differentials)",
     "proxies": ("XBRUSD", "XTIUSD")},
    {"name": "Olive oil (the extra-virgin trade price, Sfax and Jaen)",
     "venue": "the International Olive Council bulletins and the Spanish Poolred reference",
     "why": "Tunisia is a top-three world producer and a bulk exporter; no olive-oil symbol is "
            "quoted, so the campaign routes into the VEGETABLE-OIL COMPLEX through soybean with "
            "the SPANISH harvest as the control -- Spain is roughly half of world output, so a "
            "price move that is also a Spanish move is not a Tunisian mechanism",
     "regime": "n/a (a physical commodity with no broker symbol)",
     "proxies": ("SOYBEAN", "CORN", "E35")},
    {"name": "Phosphate rock, DAP and TSP (the fertiliser assessments)",
     "venue": "CRU, Argus and Profercy; licensed, terms forbid machine extraction",
     "why": "Tunisia's CPG is a world-scale producer whose output is halted by DATED LABOUR "
            "ACTIONS at Gafsa; the price itself is paywalled, so MGB-J is measured on the CROPS "
            "the fertiliser cost reaches and on CPG's own published tonnage",
     "regime": "n/a (a licensed assessment)",
     "proxies": ("WHEAT", "CORN", "SOYBEAN")},
    {"name": "Iron ore (the 62% Fe seaborne reference)",
     "venue": "the licensed index providers and the Chinese port market",
     "why": "SNIM ships from Nouadhibou on published monthly tonnage; the index is licensed and "
            "no ore symbol is quoted, so the route is the CHINESE DEMAND LEG and the industrial "
            "metals, with Australian and Brazilian shipments as the control that keeps a "
            "Mauritanian claim Mauritanian",
     "regime": "n/a (a licensed index)",
     "proxies": ("USDCNH", "XALUSD", "XCUUSD")},
    {"name": "Tunindex and the Bourse de Tunis; the Bourse d'Alger (SGBV)",
     "venue": "Bourse des Valeurs Mobilieres de Tunis; Societe de Gestion de la Bourse d'Alger",
     "why": "no CFD is quoted on either and the Algiers exchange has a handful of listings; the "
            "local tape is an OBSERVABLE and the executable leg of a Maghreb risk event is the "
            "European index complex and the frontier-stress crosses",
     "regime": "n/a (equity indices)",
     "proxies": ("E35", "FRA40", "EURTRY")},
    {"name": "Tunisian, Algerian and Mauritanian sovereign USD and EUR bonds and their CDS",
     "venue": "the international bond market",
     "why": "Tunisia's eurobond spread is where the IMF-programme decision points actually "
            "printed; Algeria has essentially no external debt and issues nothing, which is "
            "itself the fact; no Maghreb credit instrument is quoted here",
     "regime": "n/a (credit)",
     "proxies": ("EURTRY", "USDTRY", "EURUSD")},
    {"name": "The Libyan letter-of-credit queue and the NOC-to-CBL oil revenue transfer",
     "venue": "the Central Bank of Libya",
     "why": "every Libyan oil dollar reaches the economy through the CBL, so the GOVERNORSHIP of "
            "that bank is an oil-supply variable -- which is precisely what the August-October "
            "2024 dispute demonstrated by taking roughly 700 kb/d offline",
     "regime": "n/a (an institutional flow)",
     "proxies": ("XBRUSD", "XTIUSD", "XAUUSD")},
)

# --------------------------------------------------------------------------- the central banks
#: The pack-level central bank is the Bank of Algeria, because DZD is the pack's declared
#: currency. The other three are carried in CENTRAL_BANKS: a Maghreb pack that describes one
#: monetary authority has erased a redenomination, a unification and a capital-control regime.
CENTRAL_BANK: dict[str, Any] = {
    "name": "Bank of Algeria -- بنك الجزائر / Banque d'Algerie",
    "short": "BA",
    "framework": "managed_float",
    "committee": "the Conseil de la Monnaie et du Credit (CMC), chaired by the Governor; there "
                 "is no published voting record and no minutes",
    "policy_instrument": "the reserve requirement, the liquidity absorption/injection facility "
                         "and the interbank fixing of the dinar; the policy rate is an "
                         "administered number that moves rarely",
    "mandate": "price and exchange-rate stability; there is NO announced inflation target and no "
               "scheduled rate cycle, so an 'Algerian rate surprise' is a category error. The "
               "real instrument is the DINAR's managed path and the reserve position behind it, "
               "both of which are hydrocarbon revenue in disguise",
    "decision_rule": "the CMC meets on no published calendar; decisions appear as regulations in "
                     "the Journal Officiel (JORADP) and as communiques on the bank's own site",
    "decision_calendar_rule": "NO PUBLISHED CALENDAR. The event clock this pack uses for Algeria "
                              "is the JORADP publication date and the monthly monetary "
                              "statistics, never an invented meeting list",
    "decision_dates": (),
    "dates_status": "DECLARED EMPTY ON PURPOSE. Typing a meeting list for a committee that "
                    "publishes none would manufacture events; the measurable Algerian clock is "
                    "the gazette and the daily fixing",
    "decision_time_utc": "10:00",
    "announce_local": "Africa/Algiers, UTC+1 all year -- ALGERIA KEEPS UTC+1 WITH NO DAYLIGHT "
                      "SAVING, so its clock drifts against Europe's by an hour for half the year",
    "dst_rule": "none in any of the four: Algeria and Tunisia UTC+1, Libya UTC+2, Mauritania "
                "UTC+0, all year. Europe moves and the Maghreb does not, so every cross-border "
                "session window in this pack has a winter form and a summer form",
    "minutes_lag_days": 0,
    "publication_classes": ("joradp_regulation", "monetary_statistics", "annual_report",
                            "balance_of_payments", "reserve_position", "fx_fixing"),
    "policy_rate_series": "BA:policy_rate",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "none exists; there is no published Algerian rate consensus and no "
                       "domestic sell-side that forecasts one",
    "consensus_proxy_trap": "the parallel-market premium is sometimes read as a policy "
                            "expectation. It is not: it is an IMPORT-DEMAND and "
                            "CAPITAL-CONTROL observable, and treating it as a rate view is how a "
                            "study ends up measuring the import bill",
    "reserves_clock": "foreign exchange reserves in the annual report and in IMF Article IV; "
                      "Algeria's reserves are the single most watched Maghreb number and they "
                      "are published with a long and irregular lag",
    "programme": "none; Algeria has refused IMF programmes and has essentially no external debt, "
                 "which is the fact that makes it a very different sovereign from Tunisia",
    "off_cycle": ("2017-2019 the 'financement non conventionnel' (direct central-bank financing "
                  "of the Treasury), authorised in 2017 and wound down -- a dated monetary "
                  "regime with a start and an end and an inflation consequence",),
    "root": "https://www.bank-of-algeria.dz",
}

CENTRAL_BANKS: dict[str, dict[str, Any]] = {
    "dz": {"name": "Bank of Algeria", "framework": "managed_float",
           "root": "https://www.bank-of-algeria.dz",
           "rule": "a daily interbank fixing the bank dominates; no published meeting calendar, "
                   "and a large reported parallel premium that is NOT its instrument"},
    "ly": {"name": "Central Bank of Libya -- مصرف ليبيا المركزي", "framework": "peg",
           "root": "https://cbl.gov.ly",
           "rule": "THE ONE THAT WAS TWO. Split between Tripoli and al-Bayda from 2014 until the "
                   "2023 reunification, with the two halves at times publishing different "
                   "numbers for the same aggregate. It unified the rate on 2020-12-16 at 4.48 "
                   "and devalued again in 2024; the GOVERNORSHIP dispute of August-October 2024 "
                   "is the clearest case anywhere of a central-bank event that is an OIL SUPPLY "
                   "event, because every Libyan oil dollar passes through this balance sheet"},
    "tn": {"name": "Banque Centrale de Tunisie -- البنك المركزي التونسي",
           "framework": "managed_float", "root": "https://www.bct.gov.tn",
           "rule": "publishes a daily reference rate and a scheduled Conseil d'administration; "
                   "capital controls keep the dinar non-convertible on the capital account, and "
                   "the bank's direct financing of the Treasury has been the live political "
                   "question of the IMF-programme era"},
    "mr": {"name": "Banque Centrale de Mauritanie -- البنك المركزي الموريتاني",
           "framework": "managed_float", "root": "https://www.bcm.mr",
           "rule": "runs periodic FX auctions and publishes a reference rate; it carried out the "
                   "10:1 REDENOMINATION of 2018-01-01, which is the single largest series break "
                   "in this pack and the reason `mru_redenominate` exists"},
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Bank of Algeria daily interbank dinar fixing",
     "local": "each business day, Africa/Algiers (UTC+1 all year)",
     "time_utc": "10:00", "time_utc_dst": "10:00",
     "dst_rule": "none; Algeria keeps UTC+1 all year while Europe moves twice",
     "instruments": ("EURUSD", "XBRUSD"), "window_minutes": 60,
     "why": "the official price of the dinar. It is a SESSION the central bank dominates rather "
            "than a market clearing, so the fixing is a policy statement and the parallel rate "
            "is the market's answer to it"},
    {"name": "The Square Port Said cash rate (the Algerian parallel market)",
     "local": "continuous during daylight hours in Algiers; no opening or closing print",
     "time_utc": "12:00", "time_utc_dst": "12:00", "dst_rule": "none",
     "instruments": ("EURUSD", "XAUUSD"), "window_minutes": 240,
     "why": "REPORTED, NEVER PUBLISHED. There is no authority behind this number; it reaches the "
            "desk through the press and private trackers, carries an UNRELIABLE credibility "
            "label, and is used only as a SPREAD to the official fixing"},
    {"name": "Central Bank of Libya official rate",
     "local": "set by board decision, not by a market session; Africa/Tripoli (UTC+2 all year)",
     "time_utc": "09:00", "time_utc_dst": "09:00", "dst_rule": "none; Libya is UTC+2 all year",
     "instruments": ("XBRUSD", "XAUUSD"), "window_minutes": 30,
     "why": "a STEP FUNCTION and not a path: 2020-12-16 unification at 4.48 and the 2024 "
            "devaluation are the only two moves in the modern sample, so a Libyan FX study has "
            "two events and not a series"},
    {"name": "Banque Centrale de Tunisie daily reference rate",
     "local": "each business day, Africa/Tunis (UTC+1 all year)",
     "time_utc": "11:00", "time_utc_dst": "11:00", "dst_rule": "none; Tunisia is UTC+1 all year",
     "instruments": ("EURUSD", "E35"), "window_minutes": 30,
     "why": "the euro is the dominant invoice currency for Tunisian trade, so the dinar's euro "
            "cross is the one that carries the terms of trade and the dollar cross is arithmetic"},
    {"name": "Banque Centrale de Mauritanie foreign-exchange auction",
     "local": "periodic auctions, Africa/Nouakchott (UTC+0 all year)",
     "time_utc": "11:00", "time_utc_dst": "11:00", "dst_rule": "none; Mauritania is UTC+0",
     "instruments": ("USDCNH", "EURUSD"), "window_minutes": 60,
     "why": "MAURITANIA IS ON UTC+0 and its neighbours are not, so the only Maghreb market whose "
            "local morning coincides with London's is this one"},
    {"name": "The European gas day (05:00 to 05:00 UTC) and the TSOs' entry nominations",
     "local": "06:00 to 06:00 CET in winter; the gas day is defined in UTC and does not move",
     "time_utc": "05:00", "time_utc_dst": "05:00",
     "dst_rule": "none for the gas day itself; the LOCAL clock around it moves and the gas day "
                 "does not, which is the trap in every European gas session study",
     "instruments": ("XNGUSD", "EUSTX50", "NETH25"), "window_minutes": 60,
     "why": "Transmed's entry at Mazara del Vallo and Medgaz's at Almeria are NOMINATED and then "
            "PUBLISHED against this day boundary; an Algerian flow event has a gas-day stamp and "
            "not a calendar-day one"},
    {"name": "Snam daily entry-point publication (the Transmed volume)",
     "local": "published each gas day by the Italian TSO",
     "time_utc": "06:00", "time_utc_dst": "06:00", "dst_rule": "none; the gas day is UTC-anchored",
     "instruments": ("XNGUSD", "EUSTX50"), "window_minutes": 60,
     "why": "THE MOST PRICE-RELEVANT OPEN SERIES IN THIS PACK: the daily Algerian volume arriving "
            "in Sicily, published by a European regulated monopoly with no paywall"},
    {"name": "Enagas Medgaz entry publication (the Almeria volume)",
     "local": "published each gas day by the Spanish TSO",
     "time_utc": "06:00", "time_utc_dst": "06:00", "dst_rule": "none",
     "instruments": ("XNGUSD", "E35"), "window_minutes": 60,
     "why": "the Spanish half of the Algerian export; since the Maghreb-Europe line closed on "
            "2021-10-31 this is the ONLY pipeline route from Algeria to Spain, which makes a "
            "Medgaz interruption a single-point-of-failure event"},
    {"name": "OPEC Monthly Oil Market Report secondary-source production table",
     "local": "mid-month, Vienna", "time_utc": "11:00", "time_utc_dst": "11:00",
     "dst_rule": "the OPEC release follows Vienna's clock and therefore moves with European DST",
     "instruments": ("XBRUSD", "XTIUSD"), "window_minutes": 60,
     "why": "THE ONLY CONSISTENT LIBYAN AND ALGERIAN PRODUCTION SERIES. Libya publishes through "
            "the NOC irregularly and Algeria barely at all, so the secondary-source column is "
            "the measurement and the direct-communication column is the claim"},
    {"name": "International Olive Council price and balance bulletins",
     "local": "monthly, Madrid", "time_utc": "10:00", "time_utc_dst": "09:00",
     "dst_rule": "Madrid observes European DST, so the UTC stamp moves twice a year",
     "instruments": ("SOYBEAN", "CORN", "E35"), "window_minutes": 60,
     "why": "the public reference for the olive campaign; the Tunisian crop is a world supply "
            "variable and the Spanish crop is the control that keeps it one"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "The European gas day boundary (05:00 UTC) for every pipeline flow in this pack",
     "kind": "weekday", "weekday": 0, "roll": "next", "window_utc": ("05:00", "06:00"),
     "instruments": ("XNGUSD", "EUSTX50", "NETH25"),
     "why": "the gas day is defined in UTC and DOES NOT MOVE with daylight saving, while the "
            "local clocks around it do; a flow study stamped on calendar days mislabels one hour "
            "of every day and the whole of two changeover days a year"},
    {"name": "Monthly gas nomination and capacity-booking cycle on Transmed and Medgaz",
     "kind": "month_end", "roll": "previous", "window_utc": ("05:00", "12:00"),
     "instruments": ("XNGUSD", "EUSTX50", "E35"),
     "why": "annual, quarterly and monthly capacity products are booked into the month boundary, "
            "so a change in the Algerian delivery profile appears at a scheduled moment"},
    {"name": "OPEC and Declaration of Cooperation ministerial meetings",
     "kind": "day_of_month", "days": (1, 2, 3, 4, 5), "roll": "next",
     "window_utc": ("10:00", "16:00"), "instruments": ("XBRUSD", "XTIUSD"),
     "why": "ALGERIA IS AN OPEC MEMBER WITH A QUOTA AND LIBYA IS AN OPEC MEMBER THAT IS EXEMPT "
            "FROM ONE. The exemption is the whole point: Libyan output is not a policy choice, "
            "which is why it can be used as a supply instrument and Algerian output cannot"},
    {"name": "The Tunisian olive campaign year, 1 November to 31 October",
     "kind": "day_of_month", "days": (1,), "months": (11,), "roll": "next",
     "window_utc": ("08:00", "16:00"), "instruments": ("SOYBEAN", "CORN", "E35"),
     "why": "the campaign year, not the calendar year, is the unit; a calendar-year olive study "
            "cuts every harvest in half and compares two different crops"},
    {"name": "Calendar fiscal year end, 31 December, in all four states",
     "kind": "fiscal_year_end", "roll": "previous", "window_utc": ("08:00", "16:00"),
     "instruments": ("EURUSD", "XBRUSD", "XNGUSD"),
     "why": "the Algerian loi de finances, the Tunisian budget and the Libyan budget are all "
            "dated to it, and the Algerian law's assumed oil price is the single number the "
            "whole fiscal year is built on"},
    {"name": "SNIM monthly iron-ore shipment and the Nouadhibou loading cycle",
     "kind": "month_end", "roll": "previous", "window_utc": ("08:00", "16:00"),
     "instruments": ("USDCNH", "XALUSD", "XCUUSD"),
     "why": "the ore leaves on a monthly published tonnage against contracted liftings, so the "
            "Mauritanian export is a counted physical flow and not an estimate"},
    {"name": "The month-end European gas storage and supply-security reporting boundary",
     "kind": "month_end", "roll": "previous", "window_utc": ("05:00", "12:00"),
     "instruments": ("XNGUSD", "GER40", "NETH25", "EUSTX50"),
     "why": "European storage targets are legislated in percentage terms with dated deadlines, "
            "so the value of an incremental Algerian molecule is state-dependent on the fill "
            "level at a published moment"},
    {"name": "Quarterly EU-Maghreb association-council and trade-decision points",
     "kind": "quarter_end", "roll": "previous", "window_utc": ("08:00", "16:00"),
     "instruments": ("EURUSD", "FRA40", "E35", "EUSTX50"),
     "why": "the association agreements, the migration arrangements and the energy MOUs are "
            "decided in dated council meetings; they are the political clock of the EU's "
            "southern frontier and they are published in advance"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Bourse des Valeurs Mobilieres de Tunis (BVMT) -- بورصة تونس",
     "index_symbols": (),
     "open_local": "09:00", "close_local": "14:10", "open_utc": "08:00", "close_utc": "13:10",
     "dst_rule": "none; Africa/Tunis is UTC+1 all year, so the UTC session moves against Europe "
                 "by an hour for half the year",
     "auction": "pre-opening from 09:00, continuous trading, closing auction to 14:10",
     "expiry_rule": "no listed index derivatives and no public derivatives tape; there is no "
                    "expiry clock to mine in this market",
     "holidays": "the Tunisian national calendar and the sighted feasts; THE TUNISIAN WEEKEND IS "
                 "SATURDAY-SUNDAY, which is the opposite of Algeria's and Libya's",
     "notes": "THE ONLY REAL EXCHANGE IN THIS PACK. No CFD is quoted on Tunindex; it enters as a "
              "transmission target and the executable leg of a Tunisian risk event is the "
              "European index complex and the frontier-stress crosses"},
    {"name": "Bourse d'Alger / SGBV -- بورصة الجزائر",
     "index_symbols": (),
     "open_local": "09:30", "close_local": "11:00", "open_utc": "08:30", "close_utc": "10:00",
     "dst_rule": "none; Africa/Algiers is UTC+1 all year",
     "auction": "a short call session; liquidity is negligible",
     "expiry_rule": "none; no derivatives exist",
     "holidays": "the Algerian national calendar and the sighted feasts; the Algerian weekend is "
                 "FRIDAY-SATURDAY",
     "notes": "A HANDFUL OF LISTINGS AND ALMOST NO TURNOVER. It is named because it exists and "
              "because pretending a country has no exchange is as wrong as pretending it has a "
              "market; nothing in this pack is measured on it"},
    {"name": "The Libyan Stock Market (Tripoli) -- DECLARED NON-FUNCTIONING",
     "index_symbols": (),
     "open_local": "", "close_local": "", "open_utc": "09:00", "close_utc": "11:00",
     "dst_rule": "none; Africa/Tripoli is UTC+2 all year",
     "auction": "none in practice",
     "expiry_rule": "none",
     "holidays": "n/a",
     "notes": "DECLARED ABSENT, NOT BLANK: the Libyan Stock Market has had no functioning public "
              "tape since 2011 and no continuous price series a desk can read. Every Libyan "
              "mechanism in this pack therefore terminates in CRUDE, in gold or in the dollar, "
              "and the local equity layer is named as a NO_LAWFUL_GROUND row rather than proxied"},
    {"name": "Mauritania -- NO SECURITIES EXCHANGE EXISTS",
     "index_symbols": (),
     "open_local": "", "close_local": "", "open_utc": "09:00", "close_utc": "11:00",
     "dst_rule": "none; Africa/Nouakchott is UTC+0 all year",
     "auction": "none",
     "expiry_rule": "none",
     "holidays": "n/a",
     "notes": "DECLARED ABSENT: Mauritania has no stock exchange. The country's financial ground "
              "is the central bank, SNIM's own disclosures, the mining and fisheries ministries "
              "and the multilateral record; there is no local tape and none is implied"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "maghreb_gas_day_open", "start_utc": "05:00", "end_utc": "07:00",
     "notes": "the European gas day turns at 05:00 UTC and the TSOs publish the previous day's "
              "entry volumes into the first hours of it; this is when an Algerian flow change "
              "becomes public and it does NOT move with daylight saving"},
    {"name": "maghreb_cash_morning", "start_utc": "08:00", "end_utc": "11:00",
     "notes": "the union of the Tunis and Algiers cash sessions and the two central banks' "
              "publication hours; Algeria and Tunisia are UTC+1 all year, so this window sits an "
              "hour later against Europe in summer than in winter"},
    {"name": "tripoli_announcement", "start_utc": "08:00", "end_utc": "14:00",
     "notes": "the hours in which the NOC and the CBL publish; a force-majeure declaration is a "
              "dated statement rather than a scheduled release, so the window is wide on purpose"},
    {"name": "nouakchott_morning", "start_utc": "09:00", "end_utc": "13:00",
     "notes": "MAURITANIA IS ON UTC+0, the only Maghreb clock that coincides with London's; the "
              "BCM auction and the SNIM disclosures land inside London's own morning"},
    {"name": "european_gas_afternoon", "start_utc": "12:00", "end_utc": "16:00",
     "notes": "the hours in which the European hubs actually price the day's supply news; the "
              "executable leg here is XNGUSD and the European indices, never the hub itself"},
    {"name": "opec_momr_release", "start_utc": "11:00", "end_utc": "13:00",
     "notes": "the mid-month window in which the secondary-source production table for Libya and "
              "Algeria becomes public -- the only consistent read on either"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "Snam daily entry-point volumes at Mazara del Vallo (the Transmed arrival)",
     "cadence": "daily", "time_utc": "06:00", "source": "Snam Rete Gas (Italian TSO)",
     "actual_series": "SNAM:entry_mazara", "expected_series": "UNMEASURED",
     "notes": "the single most price-relevant open series in this pack: the Algerian volume "
              "arriving in Sicily, published by a regulated European monopoly with no paywall"},
    {"name": "Enagas daily Medgaz entry volumes at Almeria",
     "cadence": "daily", "time_utc": "06:00", "source": "Enagas (Spanish TSO)",
     "actual_series": "ENAGAS:entry_almeria", "expected_series": "UNMEASURED",
     "notes": "the Spanish half of the Algerian pipeline export and, since 2021-10-31, the only "
              "pipeline route between the two countries"},
    {"name": "ENTSOG transparency platform physical flows on every Maghreb-Europe point",
     "cadence": "daily", "time_utc": "07:00", "source": "ENTSOG",
     "actual_series": "ENTSOG:physical_flow", "expected_series": "n/a",
     "notes": "the pan-European aggregation of the same data, which is how a Transmed change is "
              "separated from a Norwegian or Russian one on the same day"},
    {"name": "NOC force-majeure declarations and lift-of-force-majeure statements, by terminal",
     "cadence": "irregular", "time_utc": "12:00", "source": "National Oil Corporation of Libya",
     "actual_series": "NOC:force_majeure", "expected_series": "n/a",
     "notes": "DATED, NAMED AND PUBLISHED: Es Sider, Ras Lanuf, Zueitina, Brega and Hariga are "
              "declared individually, which is what makes a per-terminal cell possible"},
    {"name": "NOC published production and export revenue statements",
     "cadence": "irregular", "time_utc": "12:00", "source": "National Oil Corporation of Libya",
     "actual_series": "NOC:production", "expected_series": "OPEC:mom_production",
     "notes": "irregular and politically contested; the OPEC secondary-source column is the "
              "measurement and this is the claim, and the pack keeps both"},
    {"name": "OPEC Monthly Oil Market Report: Algerian and Libyan production",
     "cadence": "monthly", "time_utc": "11:00", "source": "OPEC Secretariat",
     "actual_series": "OPEC:mom_production", "expected_series": "UNMEASURED",
     "notes": "Algeria carries a quota and Libya is EXEMPT from one; the exemption is why Libyan "
              "output can be treated as a supply instrument and Algerian output cannot"},
    {"name": "Office National des Statistiques (Algeria): CPI, national accounts, industry",
     "cadence": "monthly", "time_utc": "10:00", "source": "ONS Algeria",
     "actual_series": "ONS:cpi", "expected_series": "UNMEASURED",
     "notes": "published in French and Arabic with a long lag; the CPI is the only high-frequency "
              "Algerian macro series and it is the one the subsidy politics is fought over"},
    {"name": "Direction Generale des Douanes (Algeria): monthly trade by product and partner",
     "cadence": "monthly", "time_utc": "10:00", "source": "Douanes algeriennes",
     "actual_series": "DOUANE:trade_balance", "expected_series": "UNMEASURED",
     "notes": "hydrocarbon export VALUE by destination; the Algerian half of the same flow the "
              "Italian and Spanish TSOs publish in volume, which is how the two are cross-checked"},
    {"name": "Institut National de la Statistique (Tunisia): CPI, trade, industrial production",
     "cadence": "monthly", "time_utc": "09:00", "source": "INS Tunisia",
     "actual_series": "INS:cpi", "expected_series": "UNMEASURED",
     "notes": "the most regular statistical publication in the pack; Tunisia is the one of the "
              "four whose national accounts a desk can actually use"},
    {"name": "ONAGRI olive campaign bulletins and the Tunisian oil export statistics",
     "cadence": "monthly", "time_utc": "10:00", "source": "ONAGRI (Tunisian agricultural "
                                                          "observatory)",
     "actual_series": "ONAGRI:olive_campaign", "expected_series": "IOC:balance",
     "notes": "the campaign runs 1 November to 31 October and the bulletins carry crush volumes "
              "and export tonnage through it -- a dated, weather-driven world supply series"},
    {"name": "Banque Centrale de Tunisie weekly and monthly indicators",
     "cadence": "weekly", "time_utc": "11:00", "source": "BCT",
     "actual_series": "BCT:reserves_days", "expected_series": "UNMEASURED",
     "notes": "reserves in DAYS OF IMPORTS is the number Tunisian sovereign stress is read in, "
              "and it is published weekly, which is unusually fast for this region"},
    {"name": "ANSADE (Mauritania) statistics and the SNIM production and shipment disclosures",
     "cadence": "monthly", "time_utc": "11:00", "source": "ANSADE / SNIM",
     "actual_series": "SNIM:ore_shipments", "expected_series": "UNMEASURED",
     "notes": "monthly iron-ore tonnage out of Nouadhibou; the physical counterpart of every "
              "Mauritanian claim in this pack"},
    {"name": "Ministere du Petrole, des Mines et de l'Energie (Mauritania): GTA milestones",
     "cadence": "irregular", "time_utc": "11:00", "source": "petrole.gov.mr and the operators",
     "actual_series": "GTA:capacity_mtpa", "expected_series": "n/a",
     "notes": "Greater Tortue Ahmeyim is SHARED WITH SENEGAL, so the milestone dates belong to "
              "this pack and to `west_africa` at once and neither may claim them alone"},
    {"name": "IMF Article IV and programme reviews for Tunisia, Mauritania, Algeria and Libya",
     "cadence": "annual", "time_utc": "14:00", "source": "International Monetary Fund",
     "actual_series": "IMF:article_iv", "expected_series": "n/a",
     "notes": "THE SUBSTITUTE GROUND. Where a national statistics office does not publish -- "
              "Libya's national accounts since 2011, Mauritania's fiscal detail -- the Article "
              "IV staff report is the lawful, citable series, and it is labelled as an ESTIMATE"},
    {"name": "UN Panel of Experts on Libya reports and Security Council documents",
     "cadence": "annual", "time_utc": "15:00", "source": "United Nations",
     "actual_series": "UN:libya_panel", "expected_series": "n/a",
     "notes": "the only systematic public account of Libyan oil-revenue flows, smuggling and the "
              "institutional split; PUBLIC DOCUMENTS of the Security Council, nothing more"},
)

# --------------------------------------------------------------------------- holidays and clocks
#: THE WORKING WEEK IS NOT SHARED, AND THAT IS THE FIRST THING A MAGHREB STUDY GETS WRONG.
#: Algeria moved from a Thursday-Friday weekend to FRIDAY-SATURDAY by decree with effect from
#: 14 August 2009 -- a DATED CHANGE that invalidates pooling an Algerian session study across it.
#: Libya rests Friday-Saturday. Mauritania's administration rests Friday-Saturday. TUNISIA IS THE
#: EXCEPTION: it keeps the Western SATURDAY-SUNDAY weekend, which is why Tunisian and Algerian
#: business days differ on two days out of seven even though the two countries share a border, a
#: language, a time zone and a pipeline.
WEEKEND_BY_JURISDICTION: dict[str, tuple[int, ...]] = {
    "dz": (4, 5),      # Friday, Saturday -- by decree, effective 2009-08-14
    "ly": (4, 5),      # Friday, Saturday
    "tn": (5, 6),      # Saturday, Sunday -- the only Western weekend in the pack
    "mr": (4, 5),      # Friday, Saturday
}
#: The pack-level answer, for a framework field that can hold only one: the UNION, because a day
#: that is a weekend somewhere in this pack is a day on which part of the ground is dark. The
#: per-jurisdiction map above is the authority and `is_session_day` is how a study uses it.
WEEKEND_WEEKDAYS: tuple[int, ...] = (4, 5, 6)
ALGERIAN_WEEKEND_CHANGE = date(2009, 8, 14)

#: FIXED SOLAR NATIONAL DAYS, PER JURISDICTION, derived rather than typed into a year table.
#: Row: (month, day, name).
FIXED_NATIONAL: dict[str, tuple[tuple[int, int, str], ...]] = {
    "dz": ((1, 1, "New Year / رأس السنة الميلادية"),
           (1, 12, "Yennayer, the Amazigh new year / ⵢⴻⵏⵏⴰⵢⴻⵔ / رأس السنة الأمازيغية"),
           (5, 1, "Labour Day / عيد العمال"),
           (7, 5, "Independence Day / عيد الاستقلال"),
           (11, 1, "Revolution Day (1954) / ثورة أول نوفمبر")),
    "ly": ((2, 17, "Revolution Day (2011) / ثورة 17 فبراير"),
           (12, 24, "Independence Day (1951) / عيد الاستقلال")),
    "tn": ((1, 1, "New Year / رأس السنة الميلادية"),
           (1, 14, "Revolution and Youth Day / عيد الثورة والشباب"),
           (3, 20, "Independence Day / عيد الاستقلال"),
           (4, 9, "Martyrs' Day / عيد الشهداء"),
           (5, 1, "Labour Day / عيد الشغل"),
           (7, 25, "Republic Day / عيد الجمهورية"),
           (8, 13, "Women's Day / عيد المرأة"),
           (10, 15, "Evacuation Day / عيد الجلاء")),
    "mr": ((1, 1, "New Year / رأس السنة الميلادية"),
           (5, 1, "Labour Day / عيد العمال"),
           (11, 28, "Independence Day / عيد الاستقلال")),
}

#: YENNAYER IS AN ALGERIAN STATUTORY HOLIDAY AND A REGIONAL OBSERVANCE, AND THE TWO ARE NOT THE
#: SAME THING. It became an official paid public holiday in ALGERIA by presidential decision at
#: the end of 2017, first observed on 12 January 2018 -- a dated addition to a market calendar,
#: which is exactly the kind of fact a pack exists to hold, because a calendar built before 2018
#: has a trading day where a calendar built after it has a closure. Amazigh communities in Libya
#: (Nafusa, Zuwara) and Tunisia (Djerba, Matmata) observe it WITHOUT a statutory closure, and
#: Mauritania does not observe it at all -- Mauritania is not an Amazigh-speaking country, and
#: its own non-Arabic ground is Hassaniya, Pulaar, Soninke and Wolof. Claiming Yennayer for
#: Mauritania would put a closure in a calendar that has none.
YENNAYER_STATUTORY_FROM: dict[str, int] = {"dz": 2018}
YENNAYER_OBSERVED_NOT_STATUTORY: tuple[str, ...] = ("ly", "tn")

#: WHO SIGHTS THE MOON, BY STATE. A Hijri date is an ANNOUNCEMENT by a named authority on the
#: evening before, not an arithmetic result, and the four authorities do not always agree with
#: each other or with the Gulf's.
SIGHTING_AUTHORITIES: dict[str, str] = {
    "dz": "وزارة الشؤون الدينية والأوقاف واللجنة الوطنية لرصد الهلال (the Algerian Ministry of "
          "Religious Affairs and the national crescent-observation commission)",
    "ly": "دار الإفتاء الليبية وهيئة الأوقاف (the Libyan fatwa house and the Awqaf authority; "
          "the two administrations have at times announced separately, which is a real risk of "
          "a one-day split inside one country)",
    "tn": "المفتي العام للجمهورية التونسية ووزارة الشؤون الدينية (the Mufti of the Republic and "
          "the Tunisian Ministry of Religious Affairs)",
    "mr": "اللجنة الوطنية لرؤية الهلال بوزارة الشؤون الإسلامية والتعليم الأصلي (the Mauritanian "
          "national crescent-sighting commission)",
}


def sighting_status(kind: str) -> str:
    """The `status` string a lunar row carries: the confidence label AND the named authority for
    each of the four states. A Hijri date is an announcement, not an algorithm, and this is how
    the table says so on every row instead of once in a footnote."""
    named = "; ".join(f"{cc}={SIGHTING_AUTHORITIES[cc]}" for cc in JURISDICTIONS)
    return f"{kind} -- sighted and announced by: {named}"


#: THE MOON-SIGHTED FEASTS, TYPED. No weekday rule and no arithmetic produces these dates. The
#: Maghreb committees have matched the Gulf's announcements in 2024 and 2025 while MOROCCO landed
#: a day later in each -- which is exactly why `ma` is the out-of-pack control for every seasonal
#: claim here. 2026 is PROJECTED throughout because no 2026 sighting has happened.
#: Row: (date, name, jurisdictions that close, status).
LUNAR_HOLIDAYS: dict[int, tuple[tuple[date, str, tuple[str, ...], str], ...]] = {
    2024: (
        (date(2024, 3, 11), "First day of Ramadan / أول أيام رمضان", ("dz", "ly", "tn", "mr"),
         sighting_status("ANNOUNCED (not a closure; the working day SHORTENS)")),
        (date(2024, 4, 10), "Eid al-Fitr day 1 / عيد الفطر", ("dz", "ly", "tn", "mr"),
         sighting_status("ANNOUNCED")),
        (date(2024, 4, 11), "Eid al-Fitr day 2 / عيد الفطر", ("dz", "ly", "tn", "mr"),
         sighting_status("ANNOUNCED")),
        (date(2024, 6, 16), "Eid al-Adha day 1 / عيد الأضحى", ("dz", "ly", "tn", "mr"),
         sighting_status("ANNOUNCED")),
        (date(2024, 6, 17), "Eid al-Adha day 2 / عيد الأضحى", ("dz", "ly", "tn", "mr"),
         sighting_status("ANNOUNCED")),
        (date(2024, 7, 7), "Hijri New Year 1446 / رأس السنة الهجرية", ("dz", "ly", "tn"),
         sighting_status("ANNOUNCED")),
        (date(2024, 7, 16), "Ashura / عاشوراء", ("dz",),
         sighting_status("ANNOUNCED -- ALGERIA ONLY of the four")),
        (date(2024, 9, 15), "Prophet's Birthday / المولد النبوي", ("dz", "ly", "tn", "mr"),
         sighting_status("ANNOUNCED")),
    ),
    2025: (
        (date(2025, 3, 1), "First day of Ramadan / أول أيام رمضان", ("dz", "ly", "tn", "mr"),
         sighting_status("ANNOUNCED (not a closure; the working day SHORTENS)")),
        (date(2025, 3, 30), "Eid al-Fitr day 1 / عيد الفطر", ("dz", "ly", "tn", "mr"),
         sighting_status("ANNOUNCED")),
        (date(2025, 3, 31), "Eid al-Fitr day 2 / عيد الفطر", ("dz", "ly", "tn", "mr"),
         sighting_status("ANNOUNCED")),
        (date(2025, 6, 6), "Eid al-Adha day 1 / عيد الأضحى", ("dz", "ly", "tn", "mr"),
         sighting_status("ANNOUNCED")),
        (date(2025, 6, 7), "Eid al-Adha day 2 / عيد الأضحى", ("dz", "ly", "tn", "mr"),
         sighting_status("ANNOUNCED")),
        (date(2025, 6, 26), "Hijri New Year 1447 / رأس السنة الهجرية", ("dz", "ly", "tn"),
         sighting_status("ANNOUNCED")),
        (date(2025, 7, 5), "Ashura / عاشوراء", ("dz",),
         sighting_status("ANNOUNCED -- ALGERIA ONLY of the four")),
        (date(2025, 9, 4), "Prophet's Birthday / المولد النبوي", ("dz", "ly", "tn", "mr"),
         sighting_status("ANNOUNCED")),
    ),
    2026: (
        (date(2026, 2, 18), "First day of Ramadan / أول أيام رمضان", ("dz", "ly", "tn", "mr"),
         sighting_status("PROJECTED (not a closure; the working day SHORTENS)")),
        (date(2026, 3, 20), "Eid al-Fitr day 1 / عيد الفطر", ("dz", "ly", "tn", "mr"),
         sighting_status("PROJECTED")),
        (date(2026, 3, 21), "Eid al-Fitr day 2 / عيد الفطر", ("dz", "ly", "tn", "mr"),
         sighting_status("PROJECTED")),
        (date(2026, 5, 27), "Eid al-Adha day 1 / عيد الأضحى", ("dz", "ly", "tn", "mr"),
         sighting_status("PROJECTED")),
        (date(2026, 5, 28), "Eid al-Adha day 2 / عيد الأضحى", ("dz", "ly", "tn", "mr"),
         sighting_status("PROJECTED")),
        (date(2026, 6, 16), "Hijri New Year 1448 / رأس السنة الهجرية", ("dz", "ly", "tn"),
         sighting_status("PROJECTED")),
        (date(2026, 6, 25), "Ashura / عاشوراء", ("dz",),
         sighting_status("PROJECTED -- ALGERIA ONLY of the four")),
        (date(2026, 8, 25), "Prophet's Birthday / المولد النبوي", ("dz", "ly", "tn", "mr"),
         sighting_status("PROJECTED")),
    ),
}

#: THE RAMADAN WORKING WINDOW, per year: (first day, last day before Eid, status). Inside it the
#: administrative day shortens across all four states and the whole publication clock moves; the
#: closure is Eid but the behaviour change is the month.
RAMADAN_WINDOWS: dict[int, tuple[date, date, str]] = {
    2024: (date(2024, 3, 11), date(2024, 4, 9), "ANNOUNCED"),
    2025: (date(2025, 3, 1), date(2025, 3, 29), "ANNOUNCED"),
    2026: (date(2026, 2, 18), date(2026, 3, 19), "PROJECTED"),
}

#: ONE-OFF DATED FACTS NO RULE PRODUCES, kept because each one is a closure or a regime moment a
#: calendar built from the rule alone would miss.
DECLARED_CLOSURES: dict[date, str] = {
    date(2024, 9, 15): "the Prophet's Birthday fell on a Sunday: Tunisia lost a weekend day and "
                       "Algeria, Libya and Mauritania lost a working one -- the split weekend "
                       "turns one calendar entry into two different events",
    date(2025, 1, 12): "Yennayer on a Sunday in Algeria, where Sunday is a WORKING day: the "
                       "Algerian closure landed mid-week for Tunisia's counterpart and not at all",
    date(2026, 1, 12): "Yennayer, statutory in Algeria since 2018 and observed without closure in "
                       "the Libyan and Tunisian Amazigh regions",
}

def national_holidays(year: int) -> dict[date, str]:
    """Every closed day across the four states in a year, with the states that close on it.

    THE FIXED DAYS ARE DERIVED and the moon-sighted days are TYPED, which is the honest split: 1
    November is 1 November in every year, and no arithmetic knows when the crescent was seen.
    Yennayer is derived too, but only for the jurisdiction and the years in which it is statutory.
    """
    rows: dict[date, list[str]] = {}
    for cc in JURISDICTIONS:
        for m, d, name in FIXED_NATIONAL.get(cc, ()):
            if m == 1 and d == 12 and year < YENNAYER_STATUTORY_FROM.get(cc, 9999):
                continue
            rows.setdefault(date(year, m, d), []).append(f"{cc}:{name}")
    for day, name, ccs, status in LUNAR_HOLIDAYS.get(year, ()):
        label = "ANNOUNCED" if status.startswith("ANNOUNCED") else "PROJECTED"
        rows.setdefault(day, []).append(f"{','.join(ccs)}:{name} [{label}]")
    for day, name in DECLARED_CLOSURES.items():
        if day.year == year:
            rows.setdefault(day, []).append(name)
    return {d: " | ".join(v) for d, v in sorted(rows.items())}


def holidays_for(code: str, year: int) -> dict[date, str]:
    """One jurisdiction's own closed days. An Algerian Ashura closure is not a Tunisian one, and
    a pooled 'Maghreb holiday' dummy that closes all four on it is wrong three times out of four.
    """
    cc = str(code).lower()
    out: dict[date, str] = {}
    for m, d, name in FIXED_NATIONAL.get(cc, ()):
        if m == 1 and d == 12 and year < YENNAYER_STATUTORY_FROM.get(cc, 9999):
            continue
        out[date(year, m, d)] = name
    for day, name, ccs, _status in LUNAR_HOLIDAYS.get(year, ()):
        if cc in ccs:
            out[day] = name
    return dict(sorted(out.items()))


def weekend_weekdays(code: str) -> tuple[int, ...]:
    """The rest days of ONE jurisdiction. Python's weekday(): Monday = 0 .. Sunday = 6, so
    Friday-Saturday is (4, 5) and the Tunisian Saturday-Sunday is (5, 6)."""
    return WEEKEND_BY_JURISDICTION.get(str(code).lower(), WEEKEND_WEEKDAYS)


def is_session_day(code: str, day: date) -> bool:
    """True when ONE jurisdiction's administration and market are open on `day`.

    THE FOUR DO NOT SHARE A WEEK. Tunisia rests Saturday and Sunday; Algeria, Libya and
    Mauritania rest Friday and Saturday. So Sunday is a WORKING DAY in three of the four and a
    rest day in the fourth, and Friday is the reverse -- two days out of seven differ between
    neighbours who share a border, a language, a time zone and a pipeline.
    """
    cc = str(code).lower()
    if day.weekday() in weekend_weekdays(cc):
        return False
    return day not in holidays_for(cc, day.year)


def shared_session_days(start: date, end: date) -> list[date]:
    """Days on which ALL FOUR are open at once. This is the only honest sample for a pooled
    Maghreb claim, and it is much smaller than a naive weekday filter suggests."""
    out: list[date] = []
    day = start
    while day <= end:
        if all(is_session_day(cc, day) for cc in JURISDICTIONS):
            out.append(day)
        day = date.fromordinal(day.toordinal() + 1)
    return out


def market_holidays(year: int) -> dict[date, str]:
    """Closed days that actually COST A WORKING DAY somewhere in the pack: the union minus the
    days on which every jurisdiction that observes them was resting anyway."""
    out: dict[date, str] = {}
    for day, label in national_holidays(year).items():
        costs = any(day in holidays_for(cc, year) and day.weekday() not in weekend_weekdays(cc)
                    for cc in JURISDICTIONS)
        if costs or day in DECLARED_CLOSURES:
            out[day] = label
    return out


def ramadan_window(year: int) -> tuple[date, date, str] | None:
    """The declared Ramadan working window for a year, or None when the pack has not declared
    it. Inside it the administrative day shortens in all four states."""
    return RAMADAN_WINDOWS.get(year)


def in_ramadan(day: date) -> bool:
    """True when this date falls inside a declared Ramadan window (a SHORTENED working day)."""
    got = RAMADAN_WINDOWS.get(day.year)
    return got is not None and got[0] <= day <= got[1]


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "derived_fixed_days_plus_typed_sightings_with_a_split_working_week",
    "authority": "each state announces the Islamic feasts through its own authority the EVENING "
                 "BEFORE: Algeria's national crescent commission, the Libyan fatwa house, the "
                 "Mufti of the Tunisian Republic and the Mauritanian national commission. The "
                 "fixed national days are set by decree and never move",
    "rule": "THREE KINDS OF FACT, TREATED DIFFERENTLY ON PURPOSE. (1) THE WORKING WEEK IS SPLIT "
            "AND THE SPLIT IS THE RULE: Algeria, Libya and Mauritania rest FRIDAY AND SATURDAY "
            "while TUNISIA rests SATURDAY AND SUNDAY, so Sunday is a working day in three of the "
            "four and Friday is a working day in one. Algeria's Friday-Saturday weekend is "
            "itself DATED -- it replaced a Thursday-Friday weekend with effect from 2009-08-14, "
            "so an Algerian session study pooled across that date is aligning two different "
            "weeks. `weekend_weekdays(cc)` is the authority and `is_session_day(cc, day)` is how "
            "a study uses it; `shared_session_days` is the much smaller sample on which a POOLED "
            "Maghreb claim is honest. (2) THE FIXED SOLAR DAYS ARE DERIVED, never typed into a "
            "year table: Algeria 1 November and 5 July (plus 1 January, 1 May and YENNAYER on 12 "
            "January, statutory since 2018); Libya 17 February and 24 December; Tunisia 14 "
            "January, 20 March, 9 April, 1 May, 25 July, 13 August and 15 October; Mauritania 28 "
            "November (plus 1 January and 1 May). (3) THE ISLAMIC-CALENDAR FEASTS CANNOT BE "
            "COMPUTED AND ARE NOT: Eid al-Fitr, Eid al-Adha, the Hijri New Year, Ashura (ALGERIA "
            "ONLY of the four) and the Prophet's Birthday are fixed by a SIGHTING announced the "
            "evening before, so they are TYPED for 2024, 2025 and 2026 with every row's `status` "
            "naming all four sighting authorities. A weekday rule that pretended to produce them "
            "would be wrong by a day often enough to mislabel the event sample it exists to "
            "build; an honest typed table beats a wrong algorithm.",
    "years": (2024, 2025, 2026),
    "weekend": "SPLIT: Friday-Saturday in dz, ly and mr; Saturday-Sunday in tn. The pack-level "
               "weekly_closed is the UNION (4, 5, 6) because a day that rests somewhere is a day "
               "on which part of this ground is dark; the per-jurisdiction map is the authority",
    "weekend_by_jurisdiction": WEEKEND_BY_JURISDICTION,
    "national_rule": "see `rule`; `national_holidays(year)` is the derived-plus-typed union and "
                     "`holidays_for(code, year)` is one state's own calendar",
    "market_rule": "there is one real exchange (Tunis), a negligible one (Algiers) and two "
                   "jurisdictions with no tape at all, so the operative calendar in this pack is "
                   "the ADMINISTRATIVE one: when do the ministries, the TSO counterparties, the "
                   "customs and the central banks publish",
    "moon_sighting_rule": "DECLARED, not inferred. ANNOUNCED rows are what the authorities "
                          "announced; PROJECTED rows may be one day off. The Maghreb states "
                          "matched the Gulf in 2024 and 2025 while MOROCCO landed a day later in "
                          "each, which is why `ma` is the out-of-pack control for every seasonal "
                          "claim here and a Saudi calendar is the wrong calendar for Morocco",
    "moving_feasts": "the lunar feasts drift about eleven days earlier each solar year, so the "
                     "Ramadan behaviour season walks through the whole solar calendar in 33 "
                     "years and no month-of-year dummy can absorb it",
    "ramadan_rule": "the administrative day shortens across all four states for the month; the "
                    "closure is Eid but the publication clock changes for the whole window, see "
                    "RAMADAN_WINDOWS",
    "yennayer_rule": "YENNAYER (12 January) became a statutory paid Algerian holiday in 2018 and "
                     "is derived only from that year forward; it is OBSERVED WITHOUT CLOSURE in "
                     "the Libyan and Tunisian Amazigh regions and is not a Mauritanian day at all",
    "table": {y: {d.isoformat(): n for d, n in national_holidays(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {
        2024: sighting_status("ANNOUNCED for every lunar row; the fixed days are certain"),
        2025: sighting_status("ANNOUNCED for every lunar row; the fixed days are certain"),
        2026: sighting_status("PROJECTED for every lunar row -- no 2026 sighting has happened "
                              "and none can be announced; the fixed days are certain"),
    },
    "known_dates": {
        "2024-04-10": "Eid al-Fitr day 1 as announced in Algiers, Tripoli, Tunis and Nouakchott; "
                      "Morocco announced 10 April as well but landed a day later in other years",
        "2024-11-01": "Algerian Revolution Day, a fixed solar date and certain in every year",
        "2025-01-12": "Yennayer, statutory in Algeria since 2018 -- a calendar entry that did "
                      "NOT exist before that year",
        "2025-03-30": "Eid al-Fitr day 1; it fell on a Sunday, which is a working day in dz, ly "
                      "and mr and a rest day in tn -- one date, two different events",
        "2026-03-20": "PROJECTED Eid al-Fitr day 1; the announced date can differ by a day",
        "2026-07-05": "Algerian Independence Day, fixed and certain",
        "2026-11-28": "Mauritanian Independence Day, fixed and certain",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "per_country_fn": holidays_for,
    "session_day_fn": is_session_day,
    "weekend_fn": weekend_weekdays,
    "ramadan_fn": ramadan_window,
}


# ------------------------------------------------------------------- the pack's own mechanisms
#: THE MAGHREB-EUROPE PIPELINE MAP AS A DATED CAPACITY SCHEDULE. Each row is
#: (effective date, declared nameplate in bcm/year, what changed). A CLOSURE IS A ROW WITH ZERO
#: IN IT, which is what makes the 2021 rupture a number rather than a story.
PIPELINES: dict[str, dict[str, Any]] = {
    "transmed": {
        "name": "Transmed / Enrico Mattei (Hassi R'Mel - Tunisia - Mazara del Vallo, Sicily)",
        "jurisdictions": ("dz", "tn"), "lands_in": "Italy (PSV)",
        "tso_series": "SNAM:entry_mazara",
        "schedule": (("1983-04-01", 12.0, "first gas to Sicily"),
                     ("1994-01-01", 24.0, "the second line doubles the route"),
                     ("2008-01-01", 33.5, "compression upgrades to the declared nameplate")),
        "why": "THE LARGEST SINGLE PIPE IN THIS PACK and the one that made Algeria Italy's "
               "largest supplier after 2022; it crosses TUNISIA, which takes an in-kind royalty, "
               "so a Tunisian transit event is an Italian supply event"},
    "medgaz": {
        "name": "Medgaz (Beni Saf - Almeria), the direct undersea line to Spain",
        "jurisdictions": ("dz",), "lands_in": "Spain (PVB)",
        "tso_series": "ENAGAS:entry_almeria",
        "schedule": (("2011-03-01", 8.0, "commissioning; the first Algeria-Spain line with no "
                                         "transit country"),
                     ("2021-11-01", 10.16, "the expansion completed in the same weeks the "
                                           "Maghreb-Europe line was shut")),
        "why": "SINCE 2021-10-31 THIS IS THE ONLY PIPELINE ROUTE FROM ALGERIA TO SPAIN, which "
               "turns a route diversification into a single point of failure"},
    "meg": {
        "name": "Maghreb-Europe / Pedro Duran Farell (Hassi R'Mel - Morocco - Tarifa)",
        "jurisdictions": ("dz",), "lands_in": "Spain (PVB) via Morocco",
        "tso_series": "ENAGAS:entry_tarifa",
        "schedule": (("1996-11-01", 8.6, "first gas to Spain and Portugal through Morocco"),
                     ("2005-01-01", 12.0, "expanded declared nameplate"),
                     ("2021-11-01", 0.0, "CLOSED. Algeria did not renew the transit contract, "
                                         "which expired on 2021-10-31, in the diplomatic "
                                         "rupture with Morocco; the line has not carried "
                                         "Algerian gas westward since")),
        "why": "THE DATED EVENT THAT IS LITERALLY THE INTERACTION WITH `ma`: one signature "
               "removed about 12 bcm/y of route capacity, cut Morocco off from Algerian gas and "
               "made Spain's Algerian supply single-route -- three months before the European "
               "gas shock of 2022"},
    "greenstream": {
        "name": "Greenstream (Mellitah, Libya - Gela, Sicily)",
        "jurisdictions": ("ly",), "lands_in": "Italy (PSV)",
        "tso_series": "SNAM:entry_gela",
        "schedule": (("2004-10-01", 8.0, "first gas from the Western Libyan Gas Project"),
                     ("2005-01-01", 11.0, "declared nameplate")),
        "why": "Libya's only gas export pipe, and the one that shows that a LIBYAN outage is not "
               "only an oil event: the same political triggers interrupt the gas line into "
               "Sicily, on the same Snam entry table as the Algerian volume"},
    "galsi": {
        "name": "GALSI (Algeria - Sardinia - Tuscany) -- ANNOUNCED AND NEVER BUILT",
        "jurisdictions": ("dz",), "lands_in": "Italy (PSV), proposed",
        "tso_series": "",
        "schedule": (("2002-01-01", 0.0, "announced; studied for a decade and formally "
                                         "abandoned without a molecule ever flowing"),),
        "why": "NAMED BECAUSE IT NEVER HAPPENED. A pipeline that is announced repeatedly and "
               "never built is a standing reminder that an MOU is not capacity, and it is the "
               "placebo for every announcement-effect claim in MGB-P"},
    "tsgp": {
        "name": "Trans-Saharan Gas Pipeline (Nigeria - Niger - Algeria) -- MOU ONLY",
        "jurisdictions": ("dz",), "lands_in": "Europe, proposed",
        "tso_series": "",
        "schedule": (("2009-07-03", 0.0, "the first trilateral MOU signed in Abuja"),
                     ("2022-07-28", 0.0, "the Abuja declaration re-commits Nigeria, Niger and "
                                         "Algeria; still no construction and no capacity")),
        "why": "A DATED SEQUENCE OF ANNOUNCEMENTS WITH ZERO DELIVERED CAPACITY, which is exactly "
               "what makes it testable: if announcement effects are real in European gas, this "
               "is the cleanest treatment arm the Maghreb offers, and its outcome is known"},
}


def pipeline_capacity(pipeline: str, on: date) -> float:
    """The declared nameplate capacity in bcm/year of a named Maghreb export pipeline on a date.

    THE PACK'S FIRST MECHANISM FUNCTION, and the reason it exists is the 2021 closure: the
    Maghreb-Europe line carried a declared 12 bcm/y on 2021-10-31 and ZERO on 2021-11-01, because
    Algeria did not renew a transit contract. A capacity that goes to zero on a dated, published
    political decision is an object a desk can test; an unknown pipeline returns 0.0 rather than
    a guess, because absence is a measurement (L1.28a).
    """
    row = PIPELINES.get(str(pipeline).strip().lower())
    if row is None:
        return 0.0
    out = 0.0
    for iso, bcm, _what in row["schedule"]:
        if on >= date.fromisoformat(iso):
            out = float(bcm)
    return out


def pipeline_state(pipeline: str, on: date) -> dict[str, Any]:
    """The full state of one route on a date: capacity, the last step that set it, and whether
    the route is OPEN, CLOSED, NEVER_BUILT or NOT_YET_COMMISSIONED."""
    key = str(pipeline).strip().lower()
    row = PIPELINES.get(key)
    if row is None:
        return {"pipeline": pipeline, "known": False, "state": "UNMEASURED", "capacity_bcm": 0.0,
                "why": "this route is not in the pack's table; an unknown pipe is never assumed "
                       "to flow"}
    steps = [(date.fromisoformat(iso), float(bcm), what) for iso, bcm, what in row["schedule"]]
    past = [s for s in steps if on >= s[0]]
    if not past:
        state, cap, what = "NOT_YET_COMMISSIONED", 0.0, "before the first dated step"
    else:
        _day, cap, what = past[-1]
        if cap > 0.0:
            state = "OPEN"
        elif len(past) > 1:
            state = "CLOSED"
        else:
            state = "NEVER_BUILT"
    return {"pipeline": key, "known": True, "state": state, "capacity_bcm": cap,
            "name": str(row["name"]), "lands_in": str(row["lands_in"]),
            "jurisdictions": tuple(row["jurisdictions"]), "tso_series": str(row["tso_series"]),
            "last_step": what, "why": str(row["why"])}


def maghreb_export_capacity(on: date) -> float:
    """Total declared Maghreb-to-Europe PIPELINE capacity on a date, in bcm/year.

    This is the number the 2021 closure actually changed, and it is the state variable MGB-A and
    MGB-B condition on: about 56.7 bcm/y of route capacity before 2021-11-01 and about 44.7 after.
    """
    return round(sum(pipeline_capacity(k, on) for k in PIPELINES), 4)


#: LIBYAN OUTAGES, TYPED, BY EPISODE. Row: (start, end, what, the named terminals and fields,
#: approximate kb/d removed, status). These are DATED, PUBLISHED, NON-ECONOMIC triggers -- which
#: is the whole reason Libya is worth a domain of its own: an oil supply shock with an exogenous
#: switch is the rarest object in a commodity market, and this one is announced by name.
LIBYA_OUTAGES: tuple[tuple[date, date, str, tuple[str, ...], float, str], ...] = (
    (date(2011, 2, 17), date(2011, 10, 20),
     "the civil war: national production fell from about 1.6 mb/d to near zero and returned over "
     "the following year",
     ("all terminals",), 1600.0, "HISTORICAL"),
    (date(2013, 7, 1), date(2014, 7, 7),
     "the Petroleum Facilities Guard blockade of the eastern export terminals",
     ("Es Sider", "Ras Lanuf", "Zueitina", "Hariga"), 600.0, "HISTORICAL"),
    (date(2020, 1, 18), date(2020, 9, 18),
     "THE EIGHT-MONTH BLOCKADE: the eastern terminals and the southern fields were closed "
     "together and national output fell to roughly 100 kb/d",
     ("Es Sider", "Ras Lanuf", "Zueitina", "Brega", "Hariga", "Sharara", "El Feel"),
     1100.0, "HISTORICAL"),
    (date(2022, 4, 17), date(2022, 7, 15),
     "the parallel-government dispute: repeated shut-ins at the eastern terminals and at Sharara "
     "and El Feel",
     ("Es Sider", "Zueitina", "Sharara", "El Feel"), 600.0, "HISTORICAL"),
    (date(2024, 8, 26), date(2024, 10, 3),
     "THE CENTRAL-BANK GOVERNORSHIP DISPUTE: the eastern administration declared force majeure "
     "over the governorship of the CBL and roughly 700 kb/d went offline for weeks -- a MONETARY "
     "institution's leadership fight expressed as an oil supply shock",
     ("Es Sider", "Ras Lanuf", "Zueitina", "Brega", "Hariga", "Sharara"), 700.0, "HISTORICAL"),
)
#: The named terminals and fields, so a per-terminal cell has a vocabulary to compile against.
LIBYAN_TERMINALS: tuple[str, ...] = ("Es Sider", "Ras Lanuf", "Zueitina", "Brega", "Hariga",
                                     "Zawiya", "Mellitah", "Bouri", "Marsa al-Hariga")
LIBYAN_FIELDS: tuple[str, ...] = ("Sharara", "El Feel", "Waha", "Amal", "Abu Attifel", "Bouri",
                                  "Wafa")


def libya_outage_state(day: date) -> dict[str, Any]:
    """Which named, dated Libyan outage episode a date falls in, or NONE.

    THE PACK'S SECOND MECHANISM FUNCTION. Every episode in the table was declared publicly, by
    name, with named terminals, and every trigger was political rather than a response to price.
    That is what makes Libya usable as an instrument and it is why this returns the NAMED
    TERMINALS beside the size: a shock that hits Es Sider and not Sharara is an eastern-terminal
    event and a shock that hits both is a national one.
    """
    for start, end, what, where, kbd, status in LIBYA_OUTAGES:
        if start <= day <= end:
            return {"in_outage": True, "start": start.isoformat(), "end": end.isoformat(),
                    "what": what, "where": tuple(where), "kb_d_offline": float(kbd),
                    "status": status,
                    "why": "a DATED, PUBLISHED, NON-ECONOMIC supply interruption: the exogenous "
                           "switch an oil supply study needs and almost never has"}
    return {"in_outage": False, "start": "", "end": "", "what": "", "where": (),
            "kb_d_offline": 0.0, "status": "NONE",
            "why": "no declared episode covers this date; the pack's table is the DECLARED "
                   "episodes only and silence here is not a claim that production was normal"}


def dzd_parallel_premium(official: float, parallel: float) -> dict[str, Any]:
    """The Algerian parallel-market premium, in per cent, with its credibility label attached.

    THE PACK'S THIRD MECHANISM FUNCTION. The official dinar comes from a central-bank fixing and
    the parallel dinar from the cash market on the Square Port Said, reported only by the press
    and by private trackers. The PREMIUM is the capital-control stress state -- and it always
    travels with an UNRELIABLE label on the second leg, because no authority stands behind it.
    A non-positive rate answers UNMEASURED rather than producing a number.
    """
    try:
        off, par = float(official), float(parallel)
    except (TypeError, ValueError):
        return {"measured": False, "why": "UNMEASURED: a rate that is not a number"}
    if off <= 0.0 or par <= 0.0:
        return {"measured": False, "why": "UNMEASURED: a non-positive exchange rate is not a "
                                          "quote, and a premium computed from one is arithmetic "
                                          "about nothing"}
    premium = (par / off - 1.0) * 100.0
    if premium >= 60.0:
        band = "EXTREME"
    elif premium >= 30.0:
        band = "STRESSED"
    elif premium >= 10.0:
        band = "ELEVATED"
    else:
        band = "NORMAL"
    return {"measured": True, "official": off, "parallel": par,
            "premium_pct": round(premium, 4), "band": band,
            "credibility": "UNRELIABLE",
            "why": "the parallel leg is REPORTED by the press and by private trackers and is "
                   "published by no authority; the premium is an import-demand and "
                   "capital-control observable, never a policy expectation and never a rate view"}


#: THE TUNISIAN OLIVE CAMPAIGN runs 1 November to 31 October, and the campaign year -- not the
#: calendar year -- is the unit. A calendar-year study cuts every harvest in half.
OLIVE_CAMPAIGN_START_MONTH = 11


def olive_campaign_year(day: date) -> dict[str, Any]:
    """The Tunisian olive campaign a date belongs to, and the phase it is in.

    THE PACK'S FOURTH MECHANISM FUNCTION. Tunisia is a top-three world producer of olive oil and
    a bulk exporter, and the crop is strongly ALTERNATE-BEARING as well as rain-dependent, so the
    campaign is a real supply variable with a published, dated bulletin behind it (ONAGRI). The
    phases matter because the information arrives in them: the crop is formed in the spring, the
    harvest is counted from November, and the export price is struck through the marketing months.
    """
    year = day.year if day.month >= OLIVE_CAMPAIGN_START_MONTH else day.year - 1
    start = date(year, OLIVE_CAMPAIGN_START_MONTH, 1)
    end = date(year + 1, OLIVE_CAMPAIGN_START_MONTH, 1) - _ONE_DAY
    if day.month in (11, 12, 1):
        phase = "harvest_and_crush"
    elif day.month in (2, 3, 4, 5):
        phase = "marketing"
    else:
        phase = "carry_out_and_crop_formation"
    return {"campaign": f"{year}/{str(year + 1)[-2:]}", "start": start.isoformat(),
            "end": end.isoformat(), "phase": phase,
            "why": "the campaign year is 1 November to 31 October; the Spanish crop is roughly "
                   "half of world output and is the CONTROL that keeps a Tunisian claim Tunisian"}


_ONE_DAY = date(2001, 1, 2) - date(2001, 1, 1)

#: THE MAURITANIAN REDENOMINATION. On 2018-01-01 one new ouguiya (MRU) replaced ten old ones
#: (MRO). A level series spliced across that date is wrong by a factor of ten.
MRU_REDENOMINATION = date(2018, 1, 1)
MRU_FACTOR = 10.0


def mru_redenominate(amount: float, on: date) -> dict[str, Any]:
    """Convert an ouguiya amount stamped `on` into TODAY'S ouguiya (MRU).

    THE PACK'S FIFTH MECHANISM FUNCTION, and the reason it is a function rather than a footnote:
    the 2018-01-01 redenomination is the most dangerous kind of series break, because a LEVEL
    spliced across it is wrong by a factor of ten while a RATIO spliced across it is silently
    right -- so the error survives every sanity check that looks at growth rates.
    """
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return {"measured": False, "why": "UNMEASURED: a non-numeric amount"}
    old = on < MRU_REDENOMINATION
    return {"measured": True, "amount_in": value, "unit_in": "MRO" if old else "MRU",
            "amount_mru": round(value / MRU_FACTOR, 6) if old else round(value, 6),
            "factor": MRU_FACTOR if old else 1.0,
            "why": "MRU replaced MRO at 1:10 on 2018-01-01; a level series spliced across that "
                   "date is wrong by a factor of ten and a ratio series is silently right, which "
                   "is why the break must be applied and never inferred"}


# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "Snam daily entry-point volumes (Mazara del Vallo and Gela)",
     "root": "https://www.snam.it/en/transportation/data-business/", "fields": (
         "entry_mazara_del_vallo_mcm", "entry_gela_mcm", "national_demand_mcm", "storage_mcm"),
     "frequency": "daily", "snapshot": "each gas day", "publish_utc": "06:00", "lag_days": 1,
     "licence": "free, public (regulated transparency)", "available": True,
     "why": "THE CLOSEST THING TO A POSITIONING SERIES THIS PACK HAS, and it is better than one: "
            "it is the actual physical Algerian and Libyan volume arriving in Italy, published "
            "by a regulated monopoly with no paywall and no survey error",
     "pit_warning": "published against the GAS DAY (05:00-05:00 UTC), not the calendar day; a "
                    "calendar-day stamp mislabels one hour of every observation"},
    {"name": "Enagas published entry volumes and the Spanish gas system data",
     "root": "https://www.enagas.es/en/technical-management-system/", "fields": (
         "entry_almeria_gwh", "entry_tarifa_gwh", "lng_regas_gwh", "demand_gwh"),
     "frequency": "daily", "snapshot": "each gas day", "publish_utc": "06:00", "lag_days": 1,
     "licence": "free, public (regulated transparency)", "available": True,
     "why": "the Spanish side of the same flow; the Tarifa entry going to zero from 2021-11-01 "
            "IS the Maghreb-Europe closure, visible as a number in a European TSO's own table",
     "pit_warning": "the Tarifa point was later used in REVERSE to send Spanish gas to Morocco, "
                    "so a naive 'Tarifa flow' series changes sign and meaning after 2022"},
    {"name": "ENTSOG transparency platform physical flows",
     "root": "https://transparency.entsog.eu", "fields": ("physical_flow", "nomination",
                                                          "interruption", "firm_capacity"),
     "frequency": "daily", "snapshot": "each gas day", "publish_utc": "07:00", "lag_days": 1,
     "licence": "free, public", "available": True,
     "why": "the pan-European aggregation, which is how an Algerian flow change is separated "
            "from a Norwegian, Russian or LNG change on the same day",
     "pit_warning": "points are renamed and re-mapped over time; a long series needs the point "
                    "dictionary as of each vintage, not today's"},
    {"name": "OPEC Monthly Oil Market Report secondary-source production",
     "root": "https://www.opec.org/opec_web/en/publications/338.htm",
     "fields": ("libya_crude_kbd", "algeria_crude_kbd", "direct_communication_kbd"),
     "frequency": "monthly", "snapshot": "month", "publish_utc": "11:00", "lag_days": 15,
     "licence": "free, public", "available": True,
     "why": "the only consistent Libyan and Algerian production series; the SECONDARY-SOURCE "
            "column is the measurement and the direct-communication column is the claim",
     "pit_warning": "revised in the following month's report, so the vintage matters; Libya is "
                    "EXEMPT from a quota and Algeria is not, which changes what the number means"},
    {"name": "Qatari-style exchange positioning for the Maghreb -- THERE IS NONE",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: none of DZD, LYD, TND or MRU has a futures contract on any exchange "
            "the desk can read, and no COT line exists for any of them",
     "pit_warning": "DOES NOT EXIST. Maghreb currency positioning is UNMEASURED by name and is "
                    "never proxied by the dollar-index COT: none of these four is a dollar "
                    "instrument and two of them have a second price the COT cannot see"},
    {"name": "Algerian aggregate retail or institutional positioning",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: Algeria has no meaningful securities market, no published retail "
            "flow statistics and no licensed margin brokerage; residents may not lawfully fund "
            "an offshore margin account under exchange control",
     "pit_warning": "DOES NOT EXIST. The nearest lawful substitute is the PARALLEL-MARKET "
                    "PREMIUM as a hard-currency demand observable, carried with an UNRELIABLE "
                    "credibility label and used only as a spread"},
    {"name": "Libyan market positioning of any kind",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: the Libyan Stock Market has had no functioning public tape since "
            "2011 and there is no domestic financial market to be positioned in",
     "pit_warning": "DOES NOT EXIST. Every Libyan mechanism in this pack terminates in crude, in "
                    "gold or in the dollar, and the lawful substitutes are the OPEC "
                    "secondary-source production table, the NOC's own announcements and the UN "
                    "Panel of Experts reporting"},
    {"name": "Tunisian foreign participation and BVMT market statistics",
     "root": "https://www.bvmt.com.tn/en/statistics", "fields": ("foreign_ownership_pct",
                                                                 "turnover_tnd", "tunindex"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "10:00", "lag_days": 10,
     "licence": "free, public", "available": True,
     "why": "the one real market in the pack; the foreign-participation share dates the episodes "
            "in which external money left Tunisian risk around the IMF decision points",
     "pit_warning": "a small tape dominated by a handful of names, and capital controls mean the "
                    "foreign share is a SLOW variable; it conditions an era, never a week"},
)

# --------------------------------------------------------------------------- terminology
#: THREE WRITING SYSTEMS AND THE PACK MEANS ALL THREE. Arabic is the law, the press and the
#: religious calendar; FRENCH is the financial and technical administration of dz, tn and mr and
#: is frequently the ONLY language a central-bank bulletin or a customs tariff exists in; and
#: TIFINAGH is the script of Tamazight, official in Algeria since the 2016 constitutional
#: revision, which is how the Amazigh ground -- including Yennayer, a statutory market closure
#: since 2018 -- is actually written. A crawl in one of the three reads one third of this region.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "MGB-A": ("سوناطراك", "الغاز الطبيعي", "أنبوب الغاز", "التصدير إلى أوروبا", "حقل حاسي الرمل",
              "الغاز المسال", "سكيكدة", "أرزيو", "Sonatrach", "gazoduc Transmed",
              "Enrico Mattei", "Medgaz", "Mazara del Vallo", "point d'entree",
              "exportations de gaz", "capacite de transport", "ⵜⴰⵣⵣⵓⵍⵜ"),
    "MGB-B": ("أنبوب الغاز المغرب أوروبا", "إغلاق الأنبوب", "عقد العبور", "قطع العلاقات",
              "الأزمة الجزائرية المغربية", "gazoduc Maghreb-Europe", "GME", "Pedro Duran Farell",
              "contrat de transit", "Tarifa", "rupture des relations", "non-renouvellement",
              "fermeture du gazoduc", "crise algero-marocaine"),
    "MGB-C": ("الاستهلاك المحلي للغاز", "دعم الطاقة", "ذروة الاستهلاك", "التكييف",
              "سونلغاز", "انقطاع الكهرباء", "consommation interieure de gaz", "subvention "
              "energetique", "pic de consommation", "climatisation", "Sonelgaz", "CREG",
              "delestage", "tarif reglemente"),
    "MGB-D": ("الدينار الجزائري", "سعر الصرف الرسمي", "السوق الموازية", "سكوار بور سعيد",
              "العملة الصعبة", "بنك الجزائر", "علاوة السوق السوداء", "dinar algerien",
              "marche parallele", "Square Port Said", "cours officiel", "devise",
              "Banque d'Algerie", "prime du marche noir", "allocation touristique"),
    "MGB-E": ("المؤسسة الوطنية للنفط", "القوة القاهرة", "ميناء السدرة", "راس لانوف", "الزويتينة",
              "البريقة", "الحريقة", "إغلاق الموانئ", "National Oil Corporation",
              "force majeure", "Es Sider", "Ras Lanuf", "Zueitina", "Brega", "Hariga",
              "fermeture des terminaux", "declaration de force majeure"),
    "MGB-F": ("حقل الشرارة", "حقل الفيل", "إغلاق الحقول", "الحرس النفطي", "الإنتاج النفطي",
              "استئناف الإنتاج", "champ de Sharara", "El Feel", "arret de production",
              "garde des installations petrolieres", "reprise de la production",
              "blocus petrolier", "production libyenne"),
    "MGB-G": ("مصرف ليبيا المركزي", "محافظ المصرف المركزي", "توحيد سعر الصرف", "خفض قيمة الدينار",
              "الاعتمادات المستندية", "إيرادات النفط", "Banque centrale de Libye",
              "unification du taux de change", "devaluation du dinar libyen",
              "gouverneur de la banque centrale", "lettres de credit", "revenus petroliers"),
    "MGB-H": ("العبور", "الإتاوة العينية", "أنبوب الغاز عبر تونس", "الشركة التونسية للأنشطة "
              "البترولية", "سرقاز", "redevance en nature", "transit gazier", "ETAP", "Sergaz",
              "droit de passage", "Oued Saf Saf", "gazoduc transtunisien", "contrat de transit"),
    "MGB-I": ("زيت الزيتون", "الموسم الفلاحي", "صابة الزيتون", "العصر", "الديوان الوطني للزيت",
              "صفاقس", "التصدير", "huile d'olive", "campagne oleicole", "recolte des olives",
              "trituration", "Office National de l'Huile", "ONAGRI", "Sfax", "exportation "
              "d'huile", "annee de charge"),
    "MGB-J": ("شركة فسفاط قفصة", "الفسفاط", "المجمع الكيميائي التونسي", "الإضراب", "الاعتصام",
              "قفصة", "أسمدة", "Compagnie des Phosphates de Gafsa", "phosphate",
              "Groupe Chimique Tunisien", "greve", "sit-in", "Gafsa", "engrais", "DAP",
              "arret de production miniere"),
    "MGB-K": ("صندوق النقد الدولي", "برنامج الإصلاح", "الترقيم السيادي", "دعم المواد الأساسية",
              "العجز الميزاني", "الاقتراض الخارجي", "Fonds monetaire international",
              "programme de reformes", "notation souveraine", "subventions", "deficit "
              "budgetaire", "eurobond tunisien", "reserves en jours d'importation"),
    "MGB-L": ("الشركة الوطنية الصناعية والمنجمية", "حديد الخام", "نواذيبو", "قطار الحديد",
              "الزويرات", "التصدير إلى الصين", "SNIM", "minerai de fer", "Nouadhibou",
              "train minier", "Zouerate", "exportation vers la Chine", "teneur en fer",
              "port minéralier"),
    "MGB-M": ("الغاز الطبيعي المسال", "حقل السلحفاة الكبرى أحميم", "الإنتاج الأول",
              "الشراكة مع السنغال", "الطاقة الإنتاجية", "Grand Tortue Ahmeyim", "GTA",
              "premier gaz", "capacite de liquefaction", "partage avec le Senegal",
              "projet gazier offshore", "FLNG"),
    "MGB-N": ("الصيد البحري", "اتفاقية الصيد", "الأسطول الأوروبي", "الأخطبوط", "نواكشوط",
              "رخصة الصيد", "peche maritime", "accord de peche", "flotte europeenne",
              "poulpe", "licence de peche", "zone economique exclusive", "Nouakchott",
              "cephalopodes"),
    "MGB-O": ("مراقبة الصرف", "القابلية للتحويل", "الاحتياطيات", "الأوقية", "الدينار التونسي",
              "إعادة التقييم", "controle des changes", "convertibilite", "ouguiya",
              "dinar tunisien", "redenomination", "reserves de change", "taux de reference",
              "marche des changes interbancaire"),
    "MGB-P": ("الاتحاد الأوروبي", "اتفاق الشراكة", "الهجرة", "الهيدروجين الأخضر",
              "الطاقة الشمسية", "مذكرة تفاهم", "أنبوب الغاز العابر للصحراء", "Union europeenne",
              "accord d'association", "migration", "hydrogene vert", "energie solaire",
              "memorandum d'entente", "gazoduc transsaharien", "Desertec", "ⵜⴰⵎⴰⵣⵉⵖⵜ",
              "ⵢⴻⵏⵏⴰⵢⴻⵔ"),
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

#: Arabic, including the presentation forms the web serves.
_ARABIC_RANGES = ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF), (0xFB50, 0xFDFF),
                  (0xFE70, 0xFEFF))
#: TIFINAGH, the script of Tamazight -- official in Algeria since the 2016 constitutional
#: revision. A Maghreb pack with no Tifinagh in it has quietly decided that an official language
#: of the largest country in Africa is not a ground.
_TIFINAGH_RANGES = ((0x2D30, 0x2D7F),)
#: The FRENCH working vocabulary the pack must also carry: the central-bank bulletins, the
#: customs tariff, the statistics tables and the pipeline documentation of dz, tn and mr are
#: French-first and frequently French-only.
FRENCH_MARKERS: tuple[str, ...] = (
    "gazoduc Transmed", "Medgaz", "gazoduc Maghreb-Europe", "marche parallele", "Square Port "
    "Said", "Banque d'Algerie", "force majeure", "campagne oleicole",
    "Compagnie des Phosphates de Gafsa", "minerai de fer", "Nouadhibou", "accord de peche",
    "controle des changes", "hydrogene vert", "gazoduc transsaharien", "redevance en nature")


def has_arabic(text: str) -> bool:
    """True when the text contains at least one Arabic codepoint."""
    return any(any(lo <= ord(ch) <= hi for lo, hi in _ARABIC_RANGES) for ch in str(text))


def has_tifinagh(text: str) -> bool:
    """True when the text contains at least one Tifinagh codepoint (Tamazight)."""
    return any(any(lo <= ord(ch) <= hi for lo, hi in _TIFINAGH_RANGES) for ch in str(text))


def arabic_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return [t for terms in rows.values() for t in terms if has_arabic(t)]


def tifinagh_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return [t for terms in rows.values() for t in terms if has_tifinagh(t)]


def french_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    """Every declared French marker actually present in the terminology table."""
    rows = TERMINOLOGY if terminology is None else terminology
    flat = {t for terms in rows.values() for t in terms}
    return [m for m in FRENCH_MARKERS if any(m in t for t in flat)]


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
    labels. `queries` carry the native script, never only a translation.
    `machine_use_allowed=False` registers ground whose terms forbid extraction: never scraped,
    never omitted."""
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


def absent_jurisdiction_layer(cc: str, layer: str, reason: str, substitute: str) -> dict[str, Any]:
    """A layer that exists for the PACK but not for one of its four jurisdictions.

    THIS IS THE ROW THE BRIEF IS ABOUT. A four-country pack whose layers are all populated can
    still be hiding that one country contributes nothing to three of them. Every row here names
    the JURISDICTION, the LAYER, WHY the ground does not exist, and the LAWFUL SUBSTITUTE the
    pack uses instead -- which is worth more than a padded source list (L1.28a).
    """
    if cc not in JURISDICTIONS:
        raise ValueError(f"absent layer for {cc!r}: not one of {list(JURISDICTIONS)}")
    row = absent_layer(layer, reason)
    row.update({"id": f"absent_{cc}_{layer}", "jurisdiction": cc, "substitute": substitute,
                "label": f"NO {layer.upper()} GROUND IN {cc.upper()}"})
    return row


SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    # ---- official
    source_class(
        "mgb_dz_official", "Algeria: the Bank of Algeria, the statistics office, customs, the "
                           "energy regulator and the Journal Officiel", layer="official",
        roots=("https://www.bank-of-algeria.dz", "https://www.ons.dz", "https://www.creg.dz",
               "https://www.douane.gov.dz", "https://www.joradp.dz"),
        queries=("بنك الجزائر النشرة الإحصائية", "سعر صرف الدينار", "الجريدة الرسمية",
                 "الديوان الوطني للإحصائيات", "مؤشر أسعار الاستهلاك", "الميزان التجاري",
                 "الجمارك الجزائرية", "قانون المالية", "لجنة ضبط الكهرباء والغاز",
                 "Banque d'Algerie statistiques monetaires", "cours de change du dinar",
                 "Journal Officiel decret executif", "ONS indice des prix",
                 "balance commerciale hydrocarbures", "tarif douanier"),
        languages=("ar", "fr"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="JORADP is where an Algerian decision becomes citable and the ONS trade file is "
              "the Algerian half of the same flow the Italian and Spanish TSOs publish in "
              "volume; CREG is the regulator that documents the domestic demand constraint"),
    source_class(
        "mgb_ly_official", "Libya: the Central Bank, the National Oil Corporation and the Bureau "
                           "of Statistics and Census", layer="official",
        roots=("https://cbl.gov.ly", "https://noc.ly", "https://bsc.ly"),
        queries=("مصرف ليبيا المركزي", "المؤسسة الوطنية للنفط", "القوة القاهرة",
                 "الإنتاج النفطي اليومي", "توحيد سعر الصرف", "الإيرادات النفطية",
                 "مصلحة الإحصاء والتعداد", "الاعتمادات المستندية", "بيان المؤسسة الوطنية للنفط",
                 "National Oil Corporation statement", "force majeure lifted",
                 "Central Bank of Libya revenue statement"),
        languages=("ar", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE NOC DECLARES FORCE MAJEURE BY TERMINAL AND BY NAME, which is the single most "
              "valuable public act in this pack; the CBL publishes oil revenue with a lag and "
              "the statistics bureau has published little since 2011 -- see NO_LAWFUL_GROUND"),
    source_class(
        "mgb_tn_official", "Tunisia: the central bank, the statistics institute, the "
                           "agricultural observatory and the official gazette", layer="official",
        roots=("https://www.bct.gov.tn", "https://www.ins.tn", "http://www.onagri.nat.tn",
               "https://www.iort.gov.tn", "https://www.douane.gov.tn"),
        queries=("البنك المركزي التونسي", "المؤشرات النقدية والمالية", "احتياطي العملة الصعبة",
                 "المعهد الوطني للإحصاء", "مؤشر أسعار الاستهلاك", "الرائد الرسمي",
                 "المرصد الوطني للفلاحة", "صابة الزيتون", "الميزان التجاري التونسي",
                 "Banque Centrale de Tunisie indicateurs", "reserves en jours d'importation",
                 "INS indice des prix a la consommation", "ONAGRI campagne oleicole",
                 "Journal Officiel de la Republique Tunisienne", "douane tunisienne"),
        languages=("ar", "fr"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the most regular statistical publication in this pack; BCT reserves IN DAYS OF "
              "IMPORTS is the number Tunisian sovereign stress is read in, and ONAGRI is the "
              "only public source that counts the olive crush as it happens"),
    source_class(
        "mgb_mr_official", "Mauritania: the central bank, the statistics agency and the "
                           "petroleum, mines and energy ministry", layer="official",
        roots=("https://www.bcm.mr", "https://www.ansade.mr", "https://petrole.gov.mr"),
        queries=("البنك المركزي الموريتاني", "الأوقية", "مزاد العملة", "الوكالة الوطنية "
                 "للإحصاء", "التعداد", "وزارة البترول والمعادن والطاقة", "الغاز الطبيعي المسال",
                 "Banque Centrale de Mauritanie taux de change", "ANSADE comptes nationaux",
                 "ouguiya redenomination", "ministere du petrole des mines et de l'energie"),
        languages=("ar", "fr"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="thin but real; ANSADE is the renamed national statistics agency and the BCM is "
              "the authority for the 2018 redenomination that `mru_redenominate` applies"),
    source_class(
        "mgb_multilateral", "The multilateral record: IMF Article IV and programme reviews, "
                            "World Bank country monitors, the UN Panel of Experts on Libya and "
                            "the Security Council documents", layer="official",
        roots=("https://www.imf.org/en/Countries/DZA", "https://www.imf.org/en/Countries/TUN",
               "https://www.imf.org/en/Countries/LBY", "https://www.imf.org/en/Countries/MRT",
               "https://www.un.org/securitycouncil/sanctions/1970/panel-of-experts"),
        queries=("Algeria Article IV staff report", "Tunisia IMF programme review",
                 "Libya Article IV", "Mauritania ECF review",
                 "UN Panel of Experts Libya report", "Libya oil revenue Security Council",
                 "rapport des services du FMI", "consultation au titre de l'article IV"),
        languages=("en", "fr", "ar"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE SUBSTITUTE GROUND, and it is named as one: where Libya's national accounts "
              "stopped in 2011 and Mauritania's fiscal detail is thin, the Article IV is the "
              "lawful citable series and it is carried as an ESTIMATE, never as a statistic"),
    # ---- institutional
    source_class(
        "mgb_state_companies", "The state operators: Sonatrach and Sonelgaz, the NOC's "
                               "subsidiaries, ETAP and Sergaz, CPG and the Groupe Chimique "
                               "Tunisien, SNIM and the GTA partners", layer="institutional",
        roots=("https://sonatrach.com", "https://www.sonelgaz.dz", "https://www.etap.com.tn",
               "https://www.gct.com.tn", "https://www.snim.com"),
        queries=("سوناطراك بيان", "عقود الغاز طويلة الأجل", "شركة فسفاط قفصة الإنتاج",
                 "المجمع الكيميائي التونسي", "الشركة الوطنية الصناعية والمنجمية",
                 "Sonatrach contrat gazier", "Sonelgaz production electrique",
                 "ETAP production petroliere", "CPG production de phosphate",
                 "SNIM production minerai de fer", "Groupe Chimique Tunisien exportations"),
        languages=("ar", "fr", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public (issuer and state disclosure)",
        notes="EVERY ONE OF THESE IS AN ACTOR AND NEVER AN INSTRUMENT (two-lane order "
              "2026-09-06). Sonatrach and SNIM disclose volumes because they borrow; that "
              "disclosure is the only company-level number this pack uses"),
    source_class(
        "mgb_european_tsos", "The European transmission system operators and the transparency "
                             "platform: Snam, Enagas, ENTSOG and the regulators",
        layer="institutional",
        roots=("https://www.snam.it/en/transportation/data-business/",
               "https://www.enagas.es/en/technical-management-system/",
               "https://transparency.entsog.eu", "https://www.arera.it"),
        queries=("Snam punti di entrata Mazara del Vallo", "dati di bilanciamento gas",
                 "Enagas entradas por conexion internacional", "balance del sistema gasista",
                 "ENTSOG physical flow interconnection point", "capacite ferme point d'entree",
                 "nomination gazoduc Almeria", "flussi fisici gasdotto"),
        languages=("en", "it", "es", "fr"), access_label="OPEN_DATA",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="THE PACK'S BEST GROUND BY A DISTANCE: a regulated European monopoly publishing "
              "the DAILY PHYSICAL VOLUME of Algerian and Libyan gas with no paywall. Everything "
              "MGB-A claims is checkable here against a number nobody in the Maghreb controls"),
    source_class(
        "mgb_energy_institutions", "OPEC, the IEA and the EIA: the Monthly Oil Market Report, "
                                   "the Oil Market Report and the country analysis briefs",
        layer="institutional",
        roots=("https://www.opec.org/opec_web/en/publications/338.htm",
               "https://www.iea.org/countries", "https://www.eia.gov/international/analysis"),
        queries=("OPEC Monthly Oil Market Report secondary sources", "Libya crude production "
                 "kb/d", "Algeria OPEC quota", "IEA gas market report North Africa",
                 "EIA Libya country analysis brief", "تقرير أوبك الشهري",
                 "حصة الجزائر الإنتاجية", "rapport mensuel de l'OPEP"),
        languages=("en", "ar", "fr"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the ONLY consistent Libyan and Algerian production series; Algeria carries a "
              "quota and Libya is EXEMPT from one, which is precisely why Libyan output can be "
              "used as a supply instrument and Algerian output cannot"),
    source_class(
        "mgb_exchanges_bodies", "The Bourse de Tunis, the Conseil du Marche Financier, the "
                                "Bourse d'Alger (SGBV) and the employers' federations UTICA, "
                                "UTAP and the Algerian FCE", layer="institutional",
        roots=("https://www.bvmt.com.tn", "https://www.cmf.tn", "https://www.sgbv.dz",
               "https://www.utica.org.tn"),
        queries=("بورصة تونس مؤشر توننداكس", "هيئة السوق المالية", "بورصة الجزائر",
                 "الاتحاد التونسي للصناعة والتجارة", "الاتحاد التونسي للفلاحة والصيد البحري",
                 "BVMT statistiques du marche", "Conseil du Marche Financier visa",
                 "UTICA communique", "UTAP campagne", "SGBV cotation"),
        languages=("ar", "fr"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the farmers' and employers' federations are the cheapest leading indicator of an "
              "olive-campaign estimate and of a Gafsa labour action, because they lobby about "
              "both in dated press releases before any ministry publishes"),
    # ---- academic
    source_class(
        "mgb_maghreb_academic", "The regional research institutes and repositories: CREAD "
                                "(Algiers), ITCEQ and ITES (Tunis), Universite de Tunis El "
                                "Manar, USTHB, the Economic Research Forum, OpenAlex and CORE",
        layer="academic",
        roots=("https://www.cread.dz", "http://www.itceq.tn", "https://erf.org.eg/publications/",
               "https://openalex.org", "https://core.ac.uk"),
        queries=("سوق الصرف الموازية في الجزائر", "تحويل العملة والتضخم", "اقتصاد المحروقات",
                 "السياسة النقدية في تونس", "marche parallele des changes Algerie",
                 "pass-through du taux de change dinar", "rente petroliere et croissance",
                 "economie tunisienne ajustement", "olive oil supply response Tunisia"),
        languages=("fr", "ar", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access / publisher terms",
        notes="CREAD and ITCEQ are the two institutions that actually model the parallel market "
              "and the subsidy pass-through; every paper is a hypothesis until the desk "
              "reproduces it, and the Libyan and Mauritanian shares of this layer are thin "
              "enough to be declared (see JURISDICTION_ABSENCES)"),
    source_class(
        "mgb_energy_academic", "The energy-economics literature that models exactly this ground: "
                               "the Oxford Institute for Energy Studies, IFRI's centre for "
                               "energy, the Florence School of Regulation and the Med "
                               "dialogue programmes", layer="academic",
        roots=("https://www.oxfordenergy.org/publications/", "https://www.ifri.org/en/centre-"
               "energie-climat", "https://fsr.eui.eu/publications/"),
        queries=("Algerian gas exports to Europe OIES", "North African gas supply outlook",
                 "Libyan oil production political risk", "Mediterranean gas corridor",
                 "securite d'approvisionnement gaziere Mediterranee",
                 "hydrogene vert Afrique du Nord Europe"),
        languages=("en", "fr"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access",
        notes="OIES is where the Algerian export decline, the domestic-demand constraint and the "
              "contract structure are modelled openly; it is the mechanism source for MGB-A and "
              "MGB-C and is never a view the desk adopts"),
    # ---- practitioner
    source_class(
        "mgb_fr_practitioner", "The French-language business and desk press: TSA (Tout Sur "
                               "l'Algerie), Maghreb Emergent, Algerie Eco, Jeune Afrique, "
                               "Africa Intelligence, African Manager, Ilboursa",
        layer="practitioner",
        roots=("https://www.tsa-algerie.com/economie/", "https://maghrebemergent.com",
               "https://www.jeuneafrique.com/economie/", "https://www.ilboursa.com"),
        queries=("cours du dinar au square", "exportations de gaz algerien",
                 "contrat Sonatrach ENI", "campagne oleicole tunisienne previsions",
                 "greve a Gafsa production de phosphate", "eurobond tunisien spread",
                 "accord FMI Tunisie", "production petroliere libyenne reprise"),
        languages=("fr",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms; some paywalled",
        notes="TSA and Maghreb Emergent carry the dated contract, decree and parallel-rate news "
              "hours before any official page updates; Africa Intelligence is a subscription "
              "newsletter and is registered rather than crawled"),
    source_class(
        "mgb_energy_practitioner", "The energy price reporting agencies and trade press: Argus, "
                                   "Platts, ICIS, Montel, Energy Intelligence, LNG Prime and "
                                   "Upstream", layer="practitioner",
        roots=("https://www.argusmedia.com", "https://www.spglobal.com/commodityinsights",
               "https://www.icis.com", "https://lngprime.com"),
        queries=("Saharan Blend differential to Dated Brent", "Es Sider loading programme",
                 "TTF PSV spread Algerian supply", "Medgaz nominations",
                 "Libyan crude exports cargo count", "Sharara restart",
                 "European gas balance North African supply"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="subscription; terms forbid machine extraction",
        machine_use_allowed=False,
        notes="REGISTERED, NEVER SCRAPED. The crude differentials, the LNG markers and the "
              "European hub curves are the actual prices this pack is about and every one of "
              "them is paywalled, which is why the measurement runs on the TSOs' PHYSICAL FLOWS "
              "and on counted production instead -- the absence is named, not worked around"),
    # ---- retail ecology
    source_class(
        "mgb_retail_communities", "The Maghreb retail and diaspora communities: r/algeria, "
                                  "r/Tunisia, the Facebook currency and import groups, YouTube "
                                  "and TikTok channels in Darija and Tunisian Arabic",
        layer="retail_ecology",
        roots=("https://www.reddit.com/r/algeria/", "https://www.reddit.com/r/Tunisia/",
               "https://www.youtube.com/results?search_query=سعر+الاورو+في+الجزائر"),
        queries=("سعر الاورو اليوم في السكوار", "شحال الاورو", "كيفاش نبدل الدولار",
                 "الاستيراد من الخارج", "سعر الذهب في الجزائر اليوم", "التحويل من فرنسا",
                 "cours euro square aujourd'hui", "changer des euros en Algerie",
                 "prix de l'or Tunisie"),
        languages=("ar", "fr"), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="KEPT AT LOW WEIGHT AND NEVER A SOURCE OF EDGE, but it is the ONLY place the "
              "parallel-rate level is quoted in near real time, and the vocabulary around the "
              "cash euro and the gold counters dates the exchange-control stress episodes MGB-D "
              "and MGB-O study"),
    source_class(
        "mgb_forex_sellers", "Arabic- and French-language 'forex' signal sellers and prop-firm "
                             "affiliates targeting Algerian and Tunisian retail on Telegram, "
                             "YouTube and TikTok", layer="retail_ecology",
        roots=("https://www.youtube.com/results?search_query=forex+algerie",
               "https://t.me/s/forexalgerie"),
        queries=("فوركس الجزائر", "التداول في تونس", "تداول الذهب للمبتدئين",
                 "prop firm algerie", "signaux forex gratuits", "compte demo trading"),
        languages=("ar", "fr"), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="UNLAWFUL UNDER EXCHANGE CONTROL AND ADVERTISED ANYWAY in both Algeria and "
              "Tunisia: a resident may not fund an offshore margin account, so this ground "
              "measures an unlicensed retail base rather than a regulated flow; kept because the "
              "XAUUSD stop clusters it advertises are a real microstructure observable"),
    # ---- app ecosystem
    source_class(
        "mgb_payment_rails", "The payment and transfer rails: SATIM and the CIB/Edahabia cards "
                             "and BaridiMob in Algeria, the Tunisian monetique and e-Dinar with "
                             "Flouci and Sobflous, Bankily/Masrvi/Sedad in Mauritania and "
                             "Moamalat/Sadad in Libya", layer="app_ecosystem",
        roots=("https://www.satim.dz", "https://www.poste.dz", "https://www.monetiquetunisie.com",
               "https://www.bcm.mr"),
        queries=("الدفع الإلكتروني في الجزائر", "بريدي موب", "بطاقة الذهبية",
                 "الدفع بالهاتف في تونس", "بنكيلي التحويل", "statistiques monetique Tunisie",
                 "paiement mobile Mauritanie", "e-Dinar recharge", "SATIM transactions CIB"),
        languages=("ar", "fr"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free statistics; app stores public",
        notes="the card and wallet statistics are the closest thing to a high-frequency domestic "
              "demand series in three of the four; Mauritania's mobile-money layer is genuinely "
              "the deepest of its financial layers, which is why it is here and its retail "
              "investing layer is declared absent"),
    source_class(
        "mgb_rate_trackers", "The private parallel-rate trackers and the press tables that "
                             "publish the Square Port Said and the Libyan cash rates",
        layer="app_ecosystem",
        roots=("https://www.tsa-algerie.com/economie/", "https://devise-dz.com",
               "https://www.libyaobserver.ly"),
        queries=("سعر الصرف في السوق الموازية اليوم", "سعر الاورو في السوق السوداء",
                 "سعر الدولار في طرابلس", "cours du dinar au marche parallele",
                 "taux de change parallele Alger", "Libyan dinar black market rate"),
        languages=("ar", "fr", "en"), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="publisher and site terms",
        notes="THE CREDIBILITY LABEL IS THE POINT. No authority stands behind any of these "
              "numbers, the sampling is unknown, and the quote is a cash rate for a small "
              "ticket. They are used ONLY as the second leg of `dzd_parallel_premium`, always "
              "as a spread, and never as a level in a cell"),
    # ---- media
    source_class(
        "mgb_dz_media", "Algeria: El Watan, TSA, Liberte, Echorouk, El Khabar, APS (the state "
                        "wire) and the Ennahar and Echorouk broadcasters", layer="media",
        roots=("https://www.elwatan-dz.com", "https://www.tsa-algerie.com",
               "https://www.echoroukonline.com", "https://www.aps.dz"),
        queries=("سوناطراك عقد جديد", "أسعار المحروقات", "ارتفاع سعر الاورو",
                 "قانون المالية التكميلي", "الجزائر وإسبانيا", "الأزمة مع المغرب",
                 "exportations de gaz vers l'Italie", "accord Sonatrach ENI",
                 "communique du ministere de l'energie"),
        languages=("ar", "fr"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="APS carries the official minute of a Sonatrach contract when the company's own "
              "page carries only a photograph; TSA and El Watan report the politics of the "
              "subsidy and the parallel market that the state wire does not"),
    source_class(
        "mgb_ly_media", "Libya: Libya Herald, The Libya Observer, Al-Wasat (alwasat.ly), LANA "
                        "(the state news agency) and the Audit Bureau's published reports",
        layer="media",
        roots=("https://libyaherald.com", "https://libyaobserver.ly", "http://alwasat.ly",
               "https://lana.gov.ly"),
        queries=("القوة القاهرة في ميناء السدرة", "إغلاق حقل الشرارة", "محافظ مصرف ليبيا "
                 "المركزي", "إيرادات النفط الليبي", "استئناف التصدير",
                 "Libya oil production resumes", "NOC force majeure Es Sider",
                 "Libyan central bank governor dispute"),
        languages=("ar", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="THE FASTEST PUBLIC READ ON A LIBYAN OUTAGE. Libya Herald and the Libya Observer "
              "carry a terminal shut-in hours before the NOC statement and days before OPEC's "
              "table; they are the dating source for LIBYA_OUTAGES and they are labelled as "
              "press, not as a statistic"),
    source_class(
        "mgb_tn_mr_media", "Tunisia and Mauritania: Businessnews.com.tn, Leaders, Kapitalis, La "
                           "Presse, Mosaique FM, and Le Calame, Sahara Medias and AMI in "
                           "Nouakchott", layer="media",
        roots=("https://www.businessnews.com.tn", "https://www.leaders.com.tn",
               "https://kapitalis.com", "https://lecalame.info", "https://saharamedias.net"),
        queries=("صابة الزيتون هذا الموسم", "إضراب في الحوض المنجمي", "اتفاق مع صندوق النقد",
                 "سعر الأوقية", "صادرات الحديد", "accord avec le FMI Tunisie",
                 "production de phosphate Gafsa", "exportations d'huile d'olive",
                 "SNIM exportations minerai", "gaz GTA premier chargement"),
        languages=("ar", "fr"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="Businessnews and Kapitalis date the IMF decision points and the Gafsa stoppages; "
              "Le Calame and Sahara Medias are the only regular public read on Mauritanian "
              "mining and fisheries politics in any language"),
    # ---- archive
    source_class(
        "mgb_gazette_archives", "The gazettes and annual reports in full run: JORADP (Algeria), "
                                "IORT (Tunisia), the Libyan gazette, the central banks' annual "
                                "reports and the statistical yearbooks", layer="archive",
        roots=("https://www.joradp.dz/HAR/Index.htm", "https://www.iort.gov.tn",
               "https://www.bank-of-algeria.dz/rapports-annuels/",
               "https://www.bct.gov.tn/bct/siteprod/actualites.jsp"),
        queries=("الجريدة الرسمية أعداد سابقة", "الرائد الرسمي أرشيف",
                 "التقرير السنوي لبنك الجزائر", "الإحصائيات النقدية أرشيف",
                 "Journal Officiel archives decrets", "rapport annuel Banque d'Algerie",
                 "annuaire statistique de la Tunisie", "historique balance des paiements"),
        languages=("ar", "fr"), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="JORADP is where the 2009 weekend decree, the 2017 unconventional-financing law "
              "and every finance law become citable, and the annual reports are the only place "
              "the Algerian reserve and hydrocarbon-revenue history is reconstructible"),
    source_class(
        "mgb_wayback", "web.archive.org snapshots of noc.ly production pages, the CBL rate "
                       "table, bank-of-algeria.dz's fixing page and the ONAGRI campaign pages "
                       "that overwrite in place", layer="archive",
        roots=("https://web.archive.org/web/*/noc.ly*", "https://web.archive.org/web/*/cbl.gov.ly*",
               "https://web.archive.org/web/*/bank-of-algeria.dz*",
               "https://web.archive.org/web/*/onagri.nat.tn*"),
        queries=("noc.ly production statement archive", "cbl.gov.ly exchange rate archive",
                 "bank of algeria taux de change archive", "onagri campagne oleicole archive",
                 "أرشيف موقع المؤسسة الوطنية للنفط"),
        languages=("ar", "fr", "en"), access_label="PUBLIC_ARCHIVE", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="Internet Archive terms",
        notes="THE MAGHREB OFFICIAL WEB OVERWRITES IN PLACE. The CBL rate table, the NOC's "
              "production page and the Algerian fixing page all show TODAY and keep no history, "
              "so the only point-in-time vintage of any of them is a crawl somebody took; "
              "without this layer MGB-D, MGB-E and MGB-G are reconstructible only from press "
              "quotes"),
    # ---- physical economy
    source_class(
        "mgb_gas_flows", "The physical gas ground: ENTSOG points, Snam entry tables, Enagas "
                         "system data, the Italian and Spanish storage series and the LNG "
                         "terminal schedules at Skikda, Arzew and Bethioua",
        layer="physical_economy",
        roots=("https://transparency.entsog.eu", "https://www.snam.it/en/transportation/"
               "data-business/", "https://www.enagas.es/en/technical-management-system/",
               "https://agsi.gie.eu"),
        queries=("Mazara del Vallo entry flow", "Almeria entry point gas",
                 "Gela entry Greenstream", "AGSI storage fill level Italy Spain",
                 "GNL Skikda cargaison", "Arzew LNG loading", "فرص تحميل الغاز المسال",
                 "محطة سكيكدة لتمييع الغاز"),
        languages=("en", "it", "es", "fr", "ar"), access_label="OPEN_DATA",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="THE COUNTED PHYSICAL FLOW, which is what makes this pack's gas claims falsifiable "
              "at all: AGSI storage plus the entry points gives both the SUPPLY and the STATE it "
              "arrives into, which is what MGB-A's conditioning needs"),
    source_class(
        "mgb_ports_terminals", "The oil and mineral terminals and their public call ground: Es "
                               "Sider, Ras Lanuf, Zueitina, Brega, Hariga, Zawiya and Mellitah "
                               "in Libya; Skikda, Arzew, Bejaia and Oran in Algeria; Rades, "
                               "Sfax and Gabes in Tunisia; Nouadhibou and Nouakchott in "
                               "Mauritania", layer="physical_economy",
        roots=("https://noc.ly", "https://www.portdealger.com.dz", "https://www.ommp.nat.tn",
               "https://www.pandn.mr"),
        queries=("ميناء السدرة تحميل", "ميناء الزويتينة", "ميناء نواذيبو المعدني",
                 "ميناء رادس حركة", "ديوان البحرية التجارية والموانئ", "escale navire petrolier",
                 "port mineralier de Nouadhibou", "trafic portuaire Rades",
                 "terminal petrolier libyen"),
        languages=("ar", "fr", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="a force majeure is a statement; a BERTH THAT DOES NOT LOAD is the fact. The port "
              "and call ground is how a declared Libyan outage is separated from an announced "
              "one, and Nouadhibou is the physical counterpart of every SNIM claim"),
    source_class(
        "mgb_commodity_physical", "The physical commodity record: USGS mineral yearbooks, IFA "
                                  "fertiliser statistics, the International Olive Council, FAO "
                                  "GIEWS and AMIS, UN Comtrade and the MIRROR customs of Italy, "
                                  "Spain and China", layer="physical_economy",
        roots=("https://www.usgs.gov/centers/national-minerals-information-center",
               "https://www.internationaloliveoil.org", "https://www.fao.org/giews/",
               "https://comtradeplus.un.org"),
        queries=("USGS phosphate rock Tunisia production", "USGS iron ore Mauritania",
                 "IOC olive oil production figures Tunisia", "GIEWS Tunisia country brief",
                 "Comtrade Algeria natural gas exports Italy",
                 "China iron ore imports by origin Mauritania",
                 "importations italiennes de gaz algerien"),
        languages=("en", "fr", "es"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="public domain / free statistics",
        notes="MIRROR CUSTOMS IS THE SUBSTITUTE for everything Libya and Mauritania do not "
              "publish: what a country will not report about its exports, its buyers report "
              "about their imports, and the two are reconcilable at the tonne"),
    # ---- source graph
    source_class(
        "mgb_source_graph", "Who cites whom: NOC statement -> Reuters/Bloomberg -> Libya Herald "
                            "-> the wires; Sonatrach -> APS -> TSA -> the French press; ONAGRI "
                            "-> UTAP -> Businessnews; the Snam table -> the energy newsletters "
                            "-> the European press", layer="source_graph",
        roots=("https://www.aps.dz", "https://libyaherald.com", "https://www.tsa-algerie.com",
               "https://www.businessnews.com.tn"),
        queries=("حسب مصادر مطلعة", "نقلا عن مصدر مسؤول", "أفادت مصادر في القطاع",
                 "selon des sources concordantes", "d'apres une source proche du dossier",
                 "citant le ministere de l'energie", "according to sources familiar",
                 "as reported by the state news agency"),
        languages=("ar", "fr", "en"), access_label="PUBLIC", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="derived from the public sources above",
        notes="'حسب مصادر' and 'selon des sources' mark the unattributed leak that precedes a "
              "Libyan shut-in or an Algerian contract by a day or two; the graph is how a leak "
              "is told from a repost, and it is the only way to date an event before the "
              "gazette or the NOC prints it"),
)

#: NO LAYER IS BLANK AT THE PACK LEVEL: between them the four jurisdictions populate all ten.
#: What is NOT true is that all four populate all ten, and that is declared below instead of
#: being hidden by the aggregate.
LAYER_ABSENCES: dict[str, str] = {}

#: WHERE A LAYER EXISTS FOR THE PACK BUT NOT FOR ONE OF ITS JURISDICTIONS. Each row names the
#: country, the layer, WHY the ground does not exist, and the LAWFUL SUBSTITUTE used instead. A
#: measured NO with a named substitute is worth more than a padded source list.
JURISDICTION_ABSENCES: tuple[dict[str, Any], ...] = (
    absent_jurisdiction_layer(
        "ly", "institutional",
        "the Libyan Stock Market has had no functioning public tape since 2011, there is no "
        "domestic asset-management industry, no rating coverage and no sell-side research; the "
        "institutions that would populate this layer either do not operate or do not publish",
        "OPEC's secondary-source production table, the NOC's own announcements, the European "
        "TSOs' Greenstream entry data and the UN Panel of Experts reports"),
    absent_jurisdiction_layer(
        "ly", "academic",
        "Libyan universities have published almost no economic research with a public working "
        "paper series since 2011, and there is no national research institute producing "
        "macroeconomic analysis a desk can cite",
        "IMF Article IV and staff reports, the World Bank Libya Economic Monitor, OIES energy "
        "papers on Libyan supply, and the UN Panel of Experts' documentary record"),
    absent_jurisdiction_layer(
        "ly", "retail_ecology",
        "there is no licensed retail brokerage, no margin regime and no domestic market to be "
        "positioned in; the household financial decision in Libya is a CASH one, made against "
        "the parallel dinar and the letter-of-credit queue",
        "the parallel-rate tracking in the app_ecosystem layer and the Libyan press, both "
        "carried at UNRELIABLE credibility and used only as spreads"),
    absent_jurisdiction_layer(
        "mr", "academic",
        "Mauritania has a very small academic economics output and no public working-paper "
        "series that covers the mining, gas or fisheries economics this pack is about",
        "IMF Article IV and ECF reviews, World Bank and AfDB country work, the published "
        "evaluations of the EU-Mauritania fisheries partnership agreement, and USGS minerals"),
    absent_jurisdiction_layer(
        "mr", "retail_ecology",
        "there is no securities exchange in Mauritania, no retail investing base and no public "
        "forum ecology around financial markets; the country's household financial layer is "
        "mobile money and remittances, which is a different object",
        "the mobile-money and payment statistics in the app_ecosystem layer, plus the BCM's own "
        "monetary aggregates"),
    absent_jurisdiction_layer(
        "dz", "institutional",
        "the Bourse d'Alger has a handful of listings and negligible turnover, there is no "
        "domestic sell-side that publishes forecasts, and no Algerian institution publishes a "
        "rate or FX consensus of any kind",
        "the state companies' own disclosures (Sonatrach, Sonelgaz), CREG's regulatory filings, "
        "the European TSOs' flow data and OPEC's production table"),
)

#: WHERE THE GROUND GENUINELY DOES NOT EXIST AS A SERIES, NAMED. Not a layer absence -- a SERIES
#: absence, and each one bounds a domain rather than blocking it. This is the measured refusal
#: (L1.28a): a study that needs one of these rows answers UNMEASURED and says which one.
NO_LAWFUL_GROUND: tuple[dict[str, str], ...] = (
    {"what": "Libyan national accounts, GDP and fiscal aggregates since 2011",
     "why": "the Bureau of Statistics and Census has published little since 2011, and between "
            "2014 and 2023 the two halves of the central bank at times published different "
            "numbers for the same aggregate -- so there is not one Libyan series, there were two "
            "and neither is continuous",
     "consequence": "every Libyan domain here is built on PHYSICAL COUNTS (production, terminal "
                    "loadings, the Greenstream entry table) and on the IMF Article IV estimate, "
                    "which is carried AS AN ESTIMATE; no Libyan macro series is pooled across "
                    "2014 to 2023"},
    {"what": "a public intraday or daily tape for any Libyan or Mauritanian security",
     "why": "the Libyan Stock Market has not functioned since 2011 and Mauritania has no stock "
            "exchange at all",
     "consequence": "every Libyan and Mauritanian mechanism terminates in crude, gas, the "
                    "industrial metals, gold or the dollar; the local equity leg is UNMEASURED "
                    "by name and never proxied by a regional index"},
    {"what": "an official Algerian parallel-market exchange rate",
     "why": "no authority publishes it; the Square Port Said rate reaches the desk only through "
            "the press and through private trackers whose sampling is unknown",
     "consequence": "`dzd_parallel_premium` carries an UNRELIABLE credibility label on its "
                    "second leg by construction, is used ONLY as a spread to the official "
                    "fixing, and never enters a cell as a level"},
    {"what": "aggregate retail or institutional positioning for any of the four markets",
     "why": "no futures contract exists for DZD, LYD, TND or MRU on any exchange the desk can "
            "read, no COT line exists for any of them, and none of the four licenses retail "
            "margin brokerage",
     "consequence": "Maghreb currency positioning is UNMEASURED by name; the dollar-index COT is "
                    "NOT a proxy, because none of the four is a dollar instrument and two of "
                    "them have a second price the COT cannot see"},
    {"what": "the TTF, PSV and PVB settlement curves and the JKM LNG marker",
     "why": "the exchanges' and the price reporting agencies' terms forbid machine extraction; "
            "they are registered with machine_use_allowed=false and never fetched",
     "consequence": "MGB-A, MGB-B and MGB-M are measured on the TSOs' PUBLISHED PHYSICAL FLOWS "
                    "and on XNGUSD as the executable leg, WITH HENRY HUB AS THE CONTROL AND "
                    "NEVER AS A PROXY: the two benchmarks decoupled by an order of magnitude in "
                    "2022 and a study that substituted one for the other measured the LNG "
                    "arbitrage and reported a European supply shock"},
    {"what": "the Saharan Blend and Libyan grade differentials to Dated Brent",
     "why": "they are price-reporting-agency assessments behind a subscription whose terms "
            "forbid extraction",
     "consequence": "MGB-E and MGB-F are measured on COUNTED PRODUCTION and on the crude "
                    "benchmark; the grade differential is named as the missing leg rather than "
                    "approximated by a refinery margin"},
    {"what": "the phosphate rock, DAP and TSP price assessments",
     "why": "CRU, Argus and Profercy are licensed and their terms forbid machine extraction",
     "consequence": "MGB-J is measured on CPG's own published tonnage, on the dated labour "
                    "actions and on the CROPS the fertiliser cost reaches; the sibling `ma` pack "
                    "carries the same refusal for OCP, and the two must be mutually controlled"},
    {"what": "the seaborne iron-ore 62% Fe index",
     "why": "the index is a licensed product of a price reporting agency",
     "consequence": "MGB-L is measured on SNIM's published monthly tonnage and on CHINESE MIRROR "
                    "CUSTOMS by origin, with Australian and Brazilian shipments as the control "
                    "that keeps a Mauritanian claim Mauritanian (`au` and `cn`)"},
    {"what": "Libyan and Mauritanian detailed customs statistics",
     "why": "neither publishes a regular, machine-readable trade file at product level",
     "consequence": "MIRROR CUSTOMS from Italy, Spain, China and UN Comtrade is the lawful "
                    "substitute: what these two do not report about their exports, their buyers "
                    "report about their imports"},
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


def jurisdiction_layer_coverage() -> dict[str, dict[str, str]]:
    """Per jurisdiction: which layers this pack declares it has NO ground in, and the substitute.

    The pack-level layer table says all ten are populated, which is true and not the whole
    truth: three of the ten are populated for Libya by nobody Libyan. This is where that is said.
    """
    out: dict[str, dict[str, str]] = {cc: {} for cc in JURISDICTIONS}
    for row in JURISDICTION_ABSENCES:
        out[str(row["jurisdiction"])][str(row["layer"])] = str(row["substitute"])
    return out


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
            "jurisdiction_absences": jurisdiction_layer_coverage(),
            "no_lawful_ground": [row["what"] for row in NO_LAWFUL_GROUND],
            "rule": "ten layers, each carrying a source or named ABSENT with a reason; a layer "
                    "that exists for the PACK but not for one of its four jurisdictions is "
                    "declared per jurisdiction WITH THE LAWFUL SUBSTITUTE, because an aggregate "
                    "that is full can still hide a country that contributes nothing; fringe and "
                    "contradicted PUBLIC material is kept at low weight and never dropped; a "
                    "page whose terms forbid machine extraction is registered "
                    "machine_use_allowed=false, never scraped and never omitted; a series that "
                    "does not lawfully exist is named in NO_LAWFUL_GROUND with the domain it "
                    "bounds and the substitute it is replaced by"}


#: NATIVE QUERY TERRITORIES: what the deep-forest miner actually types, per layer. ARABIC AND
#: FRENCH ARE BOTH NATIVE HERE and neither is a convenience: the gazette, the press and the
#: religious calendar are Arabic, and the central-bank bulletin, the customs tariff and the
#: pipeline documentation are French. A single-language crawl of this region reads half of it.
QUERY_TERRITORIES: dict[str, tuple[str, ...]] = {
    "official": ("بنك الجزائر سعر الصرف اليومي", "الجريدة الرسمية الجزائرية مرسوم تنفيذي",
                 "المؤسسة الوطنية للنفط بيان القوة القاهرة", "البنك المركزي التونسي المؤشرات",
                 "المرصد الوطني للفلاحة صابة الزيتون", "البنك المركزي الموريتاني مزاد",
                 "Banque d'Algerie statistiques monetaires trimestrielles",
                 "ONAGRI bulletin campagne oleicole", "Journal Officiel tunisien loi de finances",
                 "ANSADE comptes nationaux Mauritanie"),
    "institutional": ("سوناطراك اتفاقية بيع الغاز", "شركة فسفاط قفصة الإنتاج الشهري",
                      "الشركة الوطنية الصناعية والمنجمية صادرات",
                      "Sonatrach contrat long terme ENI", "SNIM rapport annuel production",
                      "Snam punti di entrata Mazara del Vallo dati",
                      "Enagas entradas Almeria Medgaz", "ENTSOG physical flow Transmed"),
    "academic": ("السوق الموازية للصرف في الجزائر دراسة", "أثر أسعار النفط على الاقتصاد الجزائري",
                 "الاقتصاد التونسي والإصلاح الهيكلي",
                 "marche parallele des changes Algerie econometrie",
                 "pass-through taux de change dinar tunisien",
                 "Algerian gas export decline domestic demand OIES",
                 "Libyan oil production political economy"),
    "practitioner": ("سعر الاورو اليوم في السوق الموازية", "توقعات صابة الزيتون",
                     "استئناف الإنتاج في حقل الشرارة", "cours du dinar au square Port Said",
                     "previsions campagne oleicole tunisienne", "spread eurobond tunisien",
                     "Libyan crude exports cargo count", "Saharan Blend differential"),
    "retail_ecology": ("شحال الاورو اليوم", "كيفاش نشري الذهب", "سعر الدولار في السوق السوداء",
                       "changer des euros en Algerie 2026", "prix de l'or en Tunisie aujourd'hui",
                       "r/algeria currency", "forex tunisie avis"),
    "app_ecosystem": ("بريدي موب التحويل", "الدفع الإلكتروني في تونس", "بنكيلي موريتانيا",
                      "statistiques monetique Tunisie paiement", "SATIM transactions CIB",
                      "mobile money Mauritanie Bankily", "e-Dinar solde"),
    "media": ("أسعار المحروقات في الجزائر", "القوة القاهرة في ميناء السدرة",
              "الإضراب في الحوض المنجمي بقفصة", "exportations de gaz algerien vers l'Italie",
              "accord FMI Tunisie report", "Libya oil output resumes Es Sider",
              "SNIM exportations vers la Chine"),
    "archive": ("الجريدة الرسمية الجزائرية أرشيف", "الرائد الرسمي التونسي أعداد سابقة",
                "التقرير السنوي لبنك الجزائر أرشيف", "rapport annuel Banque d'Algerie archives",
                "annuaire statistique Tunisie archives", "noc.ly production archive wayback",
                "cbl.gov.ly rate table archive"),
    "physical_economy": ("ميناء السدرة تحميل ناقلة", "ميناء نواذيبو تصدير الحديد",
                         "محطة أرزيو لتمييع الغاز", "terminal petrolier de Zueitina chargement",
                         "port mineralier de Nouadhibou trafic",
                         "Mazara del Vallo entry point physical flow",
                         "AGSI storage fill Italy Spain", "USGS phosphate rock Tunisia"),
    "source_graph": ("حسب مصادر مطلعة في قطاع الطاقة", "نقلا عن وكالة الأنباء الجزائرية",
                     "أفادت مصادر في المؤسسة الوطنية للنفط",
                     "selon des sources proches du dossier", "citant le ministere de l'energie",
                     "according to sources familiar with the negotiations"),
}

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "Snam daily entry-point physical flow at Mazara del Vallo (Transmed)",
     "source": "Snam Rete Gas (Italian TSO)", "coverage": "2010 onward, every gas day",
     "frequency": "daily", "publication_lag_days": 1.0,
     "revisions": "re-stated once when metered volumes settle", "licence": "free, public",
     "history_from": "2010-01", "pit_feasible": True,
     "assets": ("XNGUSD", "EUSTX50", "EURUSD"),
     "mechanism_families": ("physical_flow", "supply_shock"),
     "how_to_fetch": "snam.it transportation data-business portal, the 'punti di entrata' daily "
                     "table; stamped on the GAS DAY (05:00-05:00 UTC) and not the calendar day, "
                     "so the vintage key is the gas day"},
    {"name": "Enagas daily entry volumes at Almeria (Medgaz) and Tarifa (the closed MEG line)",
     "source": "Enagas (Spanish TSO)", "coverage": "2011 onward, every gas day",
     "frequency": "daily", "publication_lag_days": 1.0, "revisions": "settled monthly",
     "licence": "free, public", "history_from": "2011-03", "pit_feasible": True,
     "assets": ("XNGUSD", "E35", "EURUSD"),
     "mechanism_families": ("physical_flow", "route_closure"),
     "how_to_fetch": "enagas.es technical management of the system, the daily gas balance and "
                     "international connections table; THE TARIFA SERIES GOING TO ZERO FROM "
                     "2021-11-01 IS the Maghreb-Europe closure as a number, and it later "
                     "REVERSES to send Spanish gas to Morocco, so the sign changes meaning"},
    {"name": "ENTSOG transparency physical flows on every Maghreb-Europe interconnection point",
     "source": "ENTSOG", "coverage": "2016 onward for the harmonised points",
     "frequency": "daily", "publication_lag_days": 1.0,
     "revisions": "points are re-mapped and renamed over time", "licence": "free, public",
     "history_from": "2016-01", "pit_feasible": True,
     "assets": ("XNGUSD", "NETH25", "GER40", "EUSTX50"),
     "mechanism_families": ("physical_flow", "cross_source_control"),
     "how_to_fetch": "transparency.entsog.eu API, operational data by interconnection point; "
                     "keep the POINT DICTIONARY as of each vintage, because today's map applied "
                     "to a 2017 series silently renames flows"},
    {"name": "AGSI European gas storage fill level (Italy, Spain, the EU aggregate)",
     "source": "Gas Infrastructure Europe", "coverage": "2011 onward", "frequency": "daily",
     "publication_lag_days": 1.0, "revisions": "rare", "licence": "free, public",
     "history_from": "2011-01", "pit_feasible": True,
     "assets": ("XNGUSD", "EUSTX50", "GER40", "NETH25"),
     "mechanism_families": ("state_variable", "storage"),
     "how_to_fetch": "agsi.gie.eu API; this is the STATE an incremental Algerian molecule "
                     "arrives into, and it is what makes MGB-A's conditioning honest rather than "
                     "a raw flow-to-price regression"},
    {"name": "NOC force-majeure declarations and liftings, by terminal, with dates",
     "source": "National Oil Corporation of Libya and the Libyan press",
     "coverage": "2011 onward", "frequency": "irregular, dated",
     "publication_lag_days": 0.0,
     "revisions": "a declaration is sometimes disputed by the other administration, which is "
                  "itself a data point", "licence": "free, public",
     "history_from": "2011-02", "pit_feasible": True,
     "assets": ("XBRUSD", "XTIUSD", "XNGUSD"),
     "mechanism_families": ("supply_shock", "event_reaction", "instrument"),
     "how_to_fetch": "noc.ly statements plus Libya Herald and the Libya Observer for the "
                     "same-day date stamp; `libya_outage_state(day)` is the pack's own resolved "
                     "form of the episode table"},
    {"name": "OPEC MOMR secondary-source crude production for Libya and Algeria",
     "source": "OPEC Secretariat", "coverage": "2003 onward", "frequency": "monthly",
     "publication_lag_days": 15.0, "revisions": "revised in the following report",
     "licence": "free, public", "history_from": "2003-01", "pit_feasible": True,
     "assets": ("XBRUSD", "XTIUSD"),
     "mechanism_families": ("production", "quota_compliance"),
     "how_to_fetch": "opec.org MOMR PDF, table 'Crude oil production, secondary sources'; the "
                     "SECONDARY-SOURCE column is the measurement and the direct-communication "
                     "column is the member's claim -- keep both and never average them"},
    {"name": "Bank of Algeria daily interbank dinar fixing and monthly monetary statistics",
     "source": "Bank of Algeria", "coverage": "2000 onward", "frequency": "daily fixing, "
                                                                        "monthly statistics",
     "publication_lag_days": 0.0, "revisions": "never for the fixing",
     "licence": "free, public", "history_from": "2000-01", "pit_feasible": False,
     "assets": ("EURUSD", "XBRUSD"),
     "mechanism_families": ("fixing", "capital_control"),
     "how_to_fetch": "bank-of-algeria.dz exchange-rate page; THE TABLE SHOWS TODAY AND KEEPS NO "
                     "HISTORY, so the point-in-time vintage is a daily crawl or the Wayback "
                     "snapshot -- which is why pit_feasible is false for the historic series"},
    {"name": "The Algerian parallel-market cash rate (Square Port Said), as reported",
     "source": "the Algerian press and private rate trackers", "coverage": "2015 onward, "
                                                                          "irregular",
     "frequency": "reported daily to weekly", "publication_lag_days": 0.0,
     "revisions": "none; there is nothing to revise and nothing to audit",
     "licence": "publisher and site terms", "history_from": "2015-01", "pit_feasible": False,
     "assets": ("EURUSD", "XAUUSD", "USDTRY"),
     "mechanism_families": ("capital_control", "stress_spread"),
     "how_to_fetch": "the TSA and Maghreb Emergent rate tables and the tracker sites; CARRIED AT "
                     "UNRELIABLE CREDIBILITY, used only through `dzd_parallel_premium` as a "
                     "SPREAD to the official fixing, and never as a level in a cell"},
    {"name": "Central Bank of Libya official rate steps and published oil revenue",
     "source": "Central Bank of Libya", "coverage": "2011 onward", "frequency": "irregular",
     "publication_lag_days": 30.0,
     "revisions": "the 2014-2023 split means two publishers for one series",
     "licence": "free, public", "history_from": "2011-01", "pit_feasible": False,
     "assets": ("XBRUSD", "XAUUSD"),
     "mechanism_families": ("administered_price", "institutional_flow"),
     "how_to_fetch": "cbl.gov.ly statements and the monthly revenue releases; the rate is a STEP "
                     "FUNCTION with two moves in the modern sample (2020-12-16 unification at "
                     "4.48 and the 2024 devaluation), so it is an event list and not a path"},
    {"name": "Banque Centrale de Tunisie reserves in days of imports and the daily reference rate",
     "source": "BCT", "coverage": "2005 onward", "frequency": "weekly and daily",
     "publication_lag_days": 3.0, "revisions": "minor", "licence": "free, public",
     "history_from": "2005-01", "pit_feasible": True,
     "assets": ("EURUSD", "EURTRY", "E35"),
     "mechanism_families": ("reserve_adequacy", "sovereign_stress"),
     "how_to_fetch": "bct.gov.tn financial indicators page, weekly release; RESERVES IN DAYS OF "
                     "IMPORTS is the unit Tunisian stress is actually read in and it is "
                     "published faster than any other macro number in this pack"},
    {"name": "ONAGRI olive campaign bulletins: crush volumes, production and export tonnage",
     "source": "ONAGRI (Tunisian agricultural observatory) and the Office National de l'Huile",
     "coverage": "2000 onward by campaign year", "frequency": "monthly within the campaign",
     "publication_lag_days": 20.0, "revisions": "the campaign estimate is revised through the "
                                                "harvest", "licence": "free, public",
     "history_from": "2000-11", "pit_feasible": True,
     "assets": ("SOYBEAN", "CORN", "E35"),
     "mechanism_families": ("harvest", "supply_schedule"),
     "how_to_fetch": "onagri.nat.tn agricultural statistics, the huile d'olive section; the unit "
                     "is the CAMPAIGN YEAR (1 November to 31 October) resolved by "
                     "`olive_campaign_year`, never the calendar year"},
    {"name": "International Olive Council production, balance and price series",
     "source": "International Olive Council", "coverage": "1990 onward",
     "frequency": "monthly and annual", "publication_lag_days": 30.0,
     "revisions": "annual balances are revised", "licence": "free, public",
     "history_from": "1990-01", "pit_feasible": True,
     "assets": ("SOYBEAN", "CORN", "E35"),
     "mechanism_families": ("world_balance", "control"),
     "how_to_fetch": "internationaloliveoil.org economic affairs and promotion, the newsletter "
                     "and balance tables; THE SPANISH CROP IS THE CONTROL -- Spain is roughly "
                     "half of world output, so a price move that is also a Spanish move is not "
                     "a Tunisian mechanism"},
    {"name": "CPG and Groupe Chimique Tunisien phosphate production and the Gafsa stoppage dates",
     "source": "Compagnie des Phosphates de Gafsa, GCT, the Tunisian press and UGTT statements",
     "coverage": "2008 onward", "frequency": "monthly production, irregular stoppages",
     "publication_lag_days": 30.0, "revisions": "occasional", "licence": "free, public",
     "history_from": "2008-01", "pit_feasible": True,
     "assets": ("WHEAT", "CORN", "SOYBEAN"),
     "mechanism_families": ("input_cost", "labour_action", "event_reaction"),
     "how_to_fetch": "gct.com.tn and the Businessnews/Kapitalis reporting of each sit-in and "
                     "restart; THE PRICE IS PAYWALLED (NO_LAWFUL_GROUND) so the measurement is "
                     "TONNAGE plus the dated stoppage, against the crops the fertiliser reaches"},
    {"name": "SNIM monthly iron-ore production and shipments from Nouadhibou",
     "source": "SNIM and ANSADE", "coverage": "2010 onward", "frequency": "monthly",
     "publication_lag_days": 45.0, "revisions": "annual report revises the monthly file",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": True,
     "assets": ("USDCNH", "XALUSD", "XCUUSD"),
     "mechanism_families": ("physical_flow", "export_volume"),
     "how_to_fetch": "snim.com production and annual report pages plus ANSADE's external-trade "
                     "bulletin; cross-check against CHINESE MIRROR CUSTOMS by origin, which is "
                     "the substitute when the Mauritanian file is late"},
    {"name": "Chinese customs imports by origin: iron ore and cephalopods from Mauritania",
     "source": "China customs via UN Comtrade and the GACC monthly detail",
     "coverage": "2005 onward", "frequency": "monthly", "publication_lag_days": 40.0,
     "revisions": "revised in the annual file", "licence": "free, public",
     "history_from": "2005-01", "pit_feasible": True,
     "assets": ("USDCNH", "XALUSD", "XCUUSD"),
     "mechanism_families": ("mirror_customs", "demand"),
     "how_to_fetch": "comtradeplus.un.org, reporter China, partner Mauritania, HS 2601 (iron "
                     "ore) and HS 0307 (molluscs); THE MIRROR IS THE SUBSTITUTE for what "
                     "Mauritania does not publish at product level"},
    {"name": "Italian and Spanish customs imports of Algerian and Libyan natural gas by value",
     "source": "ISTAT, Spanish customs and UN Comtrade", "coverage": "2000 onward",
     "frequency": "monthly", "publication_lag_days": 50.0, "revisions": "annual",
     "licence": "free, public", "history_from": "2000-01", "pit_feasible": True,
     "assets": ("XNGUSD", "EUSTX50", "E35", "EURUSD"),
     "mechanism_families": ("mirror_customs", "realised_price"),
     "how_to_fetch": "comtradeplus.un.org, reporters Italy and Spain, partner Algeria, HS 2711; "
                     "VALUE divided by the TSOs' VOLUME is the only public read on the price "
                     "Algeria actually realises on its pipeline contracts"},
    {"name": "Greater Tortue Ahmeyim capacity milestones and cargo announcements",
     "source": "the Mauritanian petroleum ministry, the operators' public releases and the LNG "
               "trade press", "coverage": "2015 onward, dated milestones",
     "frequency": "irregular", "publication_lag_days": 0.0,
     "revisions": "THE SCHEDULE SLIPS AND THE SLIP IS THE EVENT", "licence": "free, public",
     "history_from": "2015-01", "pit_feasible": True,
     "assets": ("XNGUSD", "XBRUSD", "EURUSD"),
     "mechanism_families": ("supply_schedule", "event_reaction"),
     "how_to_fetch": "petrole.gov.mr plus the operators' releases and LNG Prime; the field is "
                     "SHARED WITH SENEGAL, so every milestone belongs to this pack and to "
                     "`west_africa` at once and neither may claim it alone"},
    {"name": "Algerian customs monthly trade: hydrocarbon exports by product and destination",
     "source": "Direction Generale des Douanes and ONS", "coverage": "2005 onward",
     "frequency": "monthly", "publication_lag_days": 60.0, "revisions": "annual",
     "licence": "free, public", "history_from": "2005-01", "pit_feasible": True,
     "assets": ("XNGUSD", "XBRUSD", "EURUSD"),
     "mechanism_families": ("export_value", "cross_source_control"),
     "how_to_fetch": "douane.gov.dz statistics and the ONS external-trade bulletin; this is the "
                     "Algerian half of the same flow the European TSOs publish in volume, which "
                     "is how the two sides of one pipe are reconciled"},
    {"name": "IMF Article IV and programme documents for all four states",
     "source": "International Monetary Fund", "coverage": "1990 onward where a consultation "
                                                          "took place",
     "frequency": "annual or on review", "publication_lag_days": 60.0,
     "revisions": "each vintage supersedes the last", "licence": "free, public",
     "history_from": "1990-01", "pit_feasible": True,
     "assets": ("EURUSD", "EURTRY", "USDTRY"),
     "mechanism_families": ("sovereign_stress", "substitute_series"),
     "how_to_fetch": "imf.org country pages for DZA, LBY, TUN and MRT; THE SUBSTITUTE SERIES for "
                     "Libyan national accounts and Mauritanian fiscal detail, carried AS AN "
                     "ESTIMATE with the staff report's own uncertainty language attached"},
    {"name": "UN Panel of Experts on Libya reports and Security Council documents",
     "source": "United Nations Security Council", "coverage": "2011 onward",
     "frequency": "annual with interim reports", "publication_lag_days": 30.0,
     "revisions": "none; each report stands", "licence": "free, public",
     "history_from": "2011-01", "pit_feasible": True,
     "assets": ("XBRUSD", "XTIUSD", "XAUUSD"),
     "mechanism_families": ("institutional_flow", "substitute_series"),
     "how_to_fetch": "un.org Security Council 1970 committee, Panel of Experts reports; PUBLIC "
                     "DOCUMENTS ONLY, and the only systematic public account of Libyan "
                     "oil-revenue flows, smuggling and the institutional split"},
    {"name": "European association-council, energy MOU and hydrogen-corridor decision dates",
     "source": "the European Commission, the Council and the national energy ministries",
     "coverage": "1995 onward", "frequency": "irregular, dated",
     "publication_lag_days": 0.0, "revisions": "none", "licence": "free, public",
     "history_from": "1995-01", "pit_feasible": True,
     "assets": ("EURUSD", "FRA40", "GER40", "E35", "EUSTX50"),
     "mechanism_families": ("policy_event", "announcement"),
     "how_to_fetch": "consilium.europa.eu meeting calendars and the Commission's press corner, "
                     "plus the Italian, German and Spanish ministries' MOU announcements; the "
                     "GALSI and Trans-Saharan histories are the placebo arm -- announcements "
                     "with a known outcome of zero delivered capacity"},
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    # ---------------------------------------------------------------- Algeria
    {"name": "Sonatrach as the European Union's third-largest pipeline gas supplier",
     "jurisdiction": "dz",
     "holds": "the Hassi R'Mel complex, the Transmed and Medgaz export routes, the Skikda and "
              "Arzew LNG trains and a long-term contract book with Italian, Spanish, French, "
              "Turkish and Portuguese buyers",
     "forced_to": ("meet take-or-pay obligations on long-term contracts whose volumes are "
                   "agreed years in advance",
                   "supply the DOMESTIC market at an administered price before it exports",
                   "renegotiate contract prices periodically under review clauses it does not "
                   "control the timing of"),
     "when": "continuously; the contractual and nomination events cluster at the monthly and "
             "annual capacity boundaries and the Italian agreements were signed in April and "
             "July 2022",
     "information": ("its own field decline rates before any statistics office reports them",
                     "the domestic demand profile and the summer air-conditioning peak",
                     "the nomination book for the next gas day",
                     "the contract price review calendar"),
     "constraints": ("a mature Hassi R'Mel and a domestic demand that grows faster than supply",
                     "an investment budget set by the state rather than by the company",
                     "the loss of the Maghreb-Europe route from 2021-10-31",
                     "an LNG fleet and train availability that caps the flexible leg"),
     "instruments": ("XNGUSD", "EUSTX50", "E35", "EURUSD"),
     "counterparties": ("the Italian, Spanish, Portuguese, French and Turkish buyers",
                        "the European TSOs whose tables publish the arriving volume",
                        "the Algerian state as owner and as domestic customer"),
     "observables": ("the Snam Mazara del Vallo daily entry volume",
                     "the Enagas Almeria daily entry volume",
                     "Algerian customs hydrocarbon export value by destination",
                     "the dated contract and MOU announcements carried by APS"),
     "impact": "the daily European supply balance moves with this company's deliveries, and "
               "because the volume is published by a European monopoly the effect is measurable "
               "against a number nobody in Algiers controls",
     "persistence": "contract structure persists for years; a flow interruption persists for "
                    "days and is fully observable throughout",
     "falsifier": "matched gas days with the same European storage level and the same Norwegian "
                  "and LNG supply, in which the Algerian entry volume did not change; a price "
                  "effect that appears equally on those days is a European balance effect and "
                  "not an Algerian one -- and any effect that also appears at Henry Hub is a "
                  "global gas effect wearing an Algerian hat",
     "notes": "AN ACTOR AND NEVER AN INSTRUMENT (two-lane order 2026-09-06); Sonatrach is "
              "unlisted in any case, and the executable leg is the gas and the European indices"},
    {"name": "The Bank of Algeria as the manager of a dinar with two prices",
     "jurisdiction": "dz",
     "holds": "the daily interbank fixing, the reserve position built out of hydrocarbon "
              "revenue, and the exchange-control regulation that creates the second price",
     "forced_to": ("publish a fixing every business day",
                   "hold the reserve position against an import bill it does not control",
                   "administer an exchange-control regime that rations hard currency"),
     "when": "the fixing each business morning, Africa/Algiers; the monetary statistics monthly "
             "and the annual report with a long lag",
     "information": ("the true reserve position before it is published",
                     "the hard-currency allocation queue and the import licence pipeline",
                     "the Treasury's financing need"),
     "constraints": ("a revenue base that is hydrocarbon export receipts",
                     "no announced inflation target and no scheduled decision calendar",
                     "a political commitment to subsidised staple and fuel prices",
                     "a parallel market it does not control and cannot publish"),
     "instruments": ("EURUSD", "XAUUSD", "XBRUSD"),
     "counterparties": ("the commercial banks at the fixing", "the importers in the licence "
                        "queue", "the Treasury", "the cash market it does not transact with"),
     "observables": ("the daily fixing", "the monthly monetary statistics",
                     "the reported parallel rate and its spread to the fixing",
                     "the reserve series in the annual report and the Article IV"),
     "impact": "the dinar's official move is administered; the INFORMATION is in the PREMIUM, "
               "which is a hard-currency demand signal that leads the import bill and therefore "
               "the hydrocarbon revenue the state is spending",
     "persistence": "the regime persists for years; a premium episode persists for months",
     "falsifier": "the premium carries no information about the next quarter's Algerian import "
                  "volume or about EURUSD beyond what the oil price already carries, measured "
                  "with the oil price and the European cycle partialled out",
     "notes": "the parallel leg is REPORTED and never official; `dzd_parallel_premium` attaches "
              "the UNRELIABLE credibility label to every number it returns"},
    {"name": "Sonelgaz, CREG and the subsidised Algerian domestic gas customer",
     "jurisdiction": "dz",
     "holds": "the domestic transmission and distribution network and an administered tariff "
              "that is far below export parity",
     "forced_to": ("serve domestic demand BEFORE export, by law and by politics",
                   "meet a summer peak driven by air conditioning and a winter heating peak",
                   "absorb a consumption growth rate that the subsidy itself creates"),
     "when": "seasonally; the summer peak is the binding one and it coincides with the European "
             "storage-injection season, which is when a European buyer most wants the molecule",
     "information": ("the domestic load curve in real time",
                     "the generation fleet's gas burn",
                     "the tariff review discussions before they are published"),
     "constraints": ("an administered price that cannot be raised without political cost",
                     "a generation fleet that is overwhelmingly gas-fired",
                     "a population and an air-conditioning stock that both keep growing"),
     "instruments": ("XNGUSD", "EUSTX50", "XBRUSD"),
     "counterparties": ("Sonatrach as supplier", "the Algerian household and industrial "
                        "customer", "the state as the subsidy payer"),
     "observables": ("CREG's published regulatory material and Sonelgaz's generation data",
                     "the seasonal residual between Algerian production and export volume",
                     "summer temperature anomalies in the north of the country"),
     "impact": "THE CONSTRAINT ON THE EXPORT. A hot Algerian summer is a European supply event, "
               "and it is PHYSICALLY CAUSAL rather than a seasonal dummy: the molecules burned "
               "in Algiers are the molecules that do not arrive in Sicily",
     "persistence": "weeks within a season; the structural trend persists for years",
     "falsifier": "summer temperature anomalies in northern Algeria carry no information about "
                  "the Mazara del Vallo entry volume once European demand, storage and "
                  "maintenance schedules are partialled out",
     "notes": "this is the mechanism that makes the Algerian export decline a FORECASTABLE trend "
              "rather than a surprise, and it is published by the regulator"},
    {"name": "The Algerian Treasury and the loi de finances as a hydrocarbon spending rule",
     "jurisdiction": "dz",
     "holds": "the budget, the Fonds de Regulation des Recettes concept and an external debt "
              "position that is close to zero",
     "forced_to": ("publish a finance law each year with an ASSUMED oil price in it",
                   "fund the subsidy bill whatever the revenue",
                   "finance a deficit domestically, because it will not borrow externally"),
     "when": "the finance law at the calendar year boundary; supplementary laws when the oil "
             "price moves enough to force one",
     "information": ("the realised hydrocarbon revenue before the statistics show it",
                     "the true import bill", "the domestic banking system's capacity to absorb "
                                             "Treasury paper"),
     "constraints": ("a fiscal break-even oil price well above the market in most years",
                     "a refusal to take IMF money or external debt, which removes the usual "
                     "adjustment channel and leaves only the exchange rate and the import queue",
                     "a subsidy bill that is politically fixed"),
     "instruments": ("XBRUSD", "XNGUSD", "EURUSD"),
     "counterparties": ("the domestic banks", "the central bank", "the import licence holders"),
     "observables": ("the finance law's assumed oil price and its spending envelope",
                     "the JORADP publication of each law",
                     "the import-licence and tariff measures that follow a revenue shortfall"),
     "impact": "an oil shock reaches the Algerian economy as an IMPORT RESTRICTION rather than "
               "as a bond spread, because there is no bond; the observable is the licence queue "
               "and the parallel premium",
     "persistence": "a fiscal year, with the supplementary law as the mid-course correction",
     "falsifier": "finance-law publication dates carry no measurable information for EURUSD or "
                  "for the crude legs once the oil price path itself is controlled",
     "notes": "ALGERIA IS THE ANTI-TUNISIA of this pack: no external debt and no programme, so "
              "its stress is expressed in quantities and not in spreads"},
    {"name": "The Square Port Said cash changers and the Algerian import licence queue",
     "jurisdiction": "dz",
     "holds": "the hard-currency cash market that clears what the official allocation does not",
     "forced_to": ("quote a price to whoever arrives, with no authority behind it",
                   "absorb the residual demand of importers, travellers and families"),
     "when": "daylight hours, continuously; the premium widens around travel and Hajj seasons "
             "and around import-restriction announcements",
     "information": ("the real level of unmet hard-currency demand, in real time and before any "
                     "official statistic",),
     "constraints": ("no legal standing and no published record",
                     "a small ticket size that makes the quote a retail price and not a "
                     "wholesale one"),
     "instruments": ("EURUSD", "XAUUSD", "USDTRY"),
     "counterparties": ("importers outside the licence system", "travellers and the diaspora",
                        "the gold counters that are the other store of value"),
     "observables": ("the reported cash rate and its spread to the fixing",
                     "the seasonal pattern around travel and religious seasons",
                     "the retail gold premium in the same souks"),
     "impact": "the premium is the cleanest public read on Algerian hard-currency scarcity and "
               "therefore on the import path that a hydrocarbon revenue shock produces",
     "persistence": "episodes of months; the structural spread persists for years",
     "falsifier": "the premium is indistinguishable from a seasonal travel pattern once Hajj, "
                  "summer diaspora travel and the school calendar are controlled for",
     "notes": "UNRELIABLE BY CONSTRUCTION and kept anyway: it is the only near-real-time "
              "Algerian price of anything, and the pack uses it strictly as a spread"},
    # ---------------------------------------------------------------- Libya
    {"name": "The National Oil Corporation as a declarer of force majeure by terminal",
     "jurisdiction": "ly",
     "holds": "the export terminals, the joint ventures that operate the fields, and the legal "
              "power to declare force majeure on a named terminal",
     "forced_to": ("announce a force majeure publicly and by name when a terminal stops",
                   "announce the lifting the same way",
                   "route every export dollar through the Central Bank of Libya"),
     "when": "irregularly and without warning; the declarations are dated statements and the "
             "press carries them within hours",
     "information": ("which berths are loading and which are not, before anyone else",
                     "the state of the field-to-terminal pipelines",
                     "the political negotiation that will end a shut-in"),
     "constraints": ("no control over the armed and political actors who close the fields",
                     "an EXEMPTION from the OPEC quota, which removes the usual economic "
                     "incentive to restrain output",
                     "infrastructure that has been repeatedly damaged"),
     "instruments": ("XBRUSD", "XTIUSD", "XNGUSD"),
     "counterparties": ("the international joint-venture partners", "the term lifters",
                        "the Central Bank of Libya", "the two administrations"),
     "observables": ("the force-majeure declarations by terminal, with dates",
                     "the published production figure",
                     "the berth activity at Es Sider, Ras Lanuf, Zueitina, Brega and Hariga",
                     "OPEC's secondary-source production column"),
     "impact": "roughly one per cent of world supply switching on and off; the 2020 blockade "
               "removed about 1.1 mb/d for eight months and the 2024 governorship dispute about "
               "700 kb/d for weeks",
     "persistence": "days to months, and the END DATE is announced too, which gives the event a "
                    "clean close as well as a clean open",
     "falsifier": "matched windows with the same OPEC+ policy state, the same dollar path and no "
                  "Libyan declaration; a crude move on declaration days that is matched on those "
                  "days is an oil-market move and not a Libyan supply event",
     "notes": "THE CLOSEST THING TO AN INSTRUMENTAL VARIABLE THIS DESK HOLDS: the triggers are "
              "political and non-economic, the switch is announced, and essentially nobody "
              "models it systematically"},
    {"name": "The Central Bank of Libya as the single gate for every oil dollar",
     "jurisdiction": "ly",
     "holds": "the foreign exchange reserves, the letter-of-credit allocation and the official "
              "exchange rate",
     "forced_to": ("receive all NOC export revenue",
                   "allocate hard currency through a letter-of-credit system that rations it",
                   "set an official rate by board decision rather than by a market session"),
     "when": "the rate changes as a STEP: 2020-12-16 unification at 4.48 and the 2024 "
             "devaluation; revenue statements monthly and irregularly",
     "information": ("the true reserve and revenue position", "the LC queue",
                     "the political negotiation over its own governorship"),
     "constraints": ("an institution that was SPLIT between Tripoli and al-Bayda from 2014 to "
                     "2023, with two boards publishing at times different numbers",
                     "a governorship that is itself contested, which in August 2024 became an "
                     "oil supply event",
                     "no independent revenue of its own"),
     "instruments": ("XBRUSD", "XAUUSD", "USDTRY"),
     "counterparties": ("the NOC", "the two administrations", "the commercial banks and the "
                        "importers in the LC queue"),
     "observables": ("the official rate steps", "the published revenue and spending statements",
                     "the reported parallel rate and its spread",
                     "the governorship dispute as reported by the Libyan and international press"),
     "impact": "A MONETARY INSTITUTION WHOSE LEADERSHIP FIGHT IS AN OIL SUPPLY SHOCK. The "
               "August-October 2024 episode is the demonstration and it is fully dated",
     "persistence": "the rate steps are permanent; the institutional episodes last weeks",
     "falsifier": "CBL governance episodes that did NOT coincide with a production interruption; "
                  "if crude moves on those too, the channel is sentiment and not supply",
     "notes": "NO LIBYAN MACRO SERIES IS POOLED ACROSS 2014-2023 in this pack, because for those "
              "years there was no single publisher"},
    {"name": "The two Libyan administrations and the armed actors who close the fields",
     "jurisdiction": "ly",
     "holds": "physical control of the fields, the terminals and the pipelines between them",
     "forced_to": ("act publicly when they act at all: a blockade is announced, a reopening is "
                   "announced, and both are dated",),
     "when": "on political triggers with no calendar: a governorship dispute, a revenue-sharing "
             "argument, a leadership change, a local grievance",
     "information": ("their own intention to close or reopen, hours or days ahead of the market",),
     "constraints": ("a need for the revenue they are interrupting, which caps the duration",
                     "international pressure that arrives through the UN process",
                     "the physical limits of restarting a shut-in field"),
     "instruments": ("XBRUSD", "XTIUSD", "EURUSD"),
     "counterparties": ("the NOC", "the CBL", "the UN mission and the Panel of Experts",
                        "the international oil companies in the joint ventures"),
     "observables": ("the dated blockade and reopening announcements",
                     "the UN Panel of Experts reporting",
                     "the local and international press before the NOC confirms"),
     "impact": "the SWITCH behind every row of LIBYA_OUTAGES; the size is in the table and the "
               "trigger is in the press",
     "persistence": "from two weeks to eight months in the observed sample",
     "falsifier": "announcement days with no subsequent production change; if crude reacts to "
                  "those the same way, the market is trading the headline and not the barrel",
     "notes": "NOTHING IN THIS PACK TOUCHES ANY PRIVATE SYSTEM OF ANY LIBYAN PARTY. Every row "
              "here comes from public statements, public press and UN documents"},
    {"name": "The Libyan Investment Authority under an international asset freeze",
     "jurisdiction": "ly",
     "holds": "a frozen sovereign portfolio whose composition is not fully public",
     "forced_to": ("remain frozen under UN and national measures, so it cannot rebalance",),
     "when": "no clock; the freeze has held since 2011 with periodic review",
     "information": ("its own holdings, which are not published in full",),
     "constraints": ("the freeze itself, which makes it a NON-PARTICIPANT in markets it would "
                     "otherwise be a large holder in",
                     "litigation and governance disputes"),
     "instruments": ("XAUUSD", "EURUSD", "USDTRY"),
     "counterparties": ("the custodian banks", "the UN sanctions committee",
                        "the two administrations that both claim it"),
     "observables": ("the UN Panel of Experts reporting on its assets",
                     "public litigation records", "periodic Security Council decisions"),
     "impact": "the ABSENCE of a large sovereign buyer is itself a market fact for the assets it "
               "holds, and it is the reason Libya has no sovereign-fund flow channel of the kind "
               "the Gulf packs carry",
     "persistence": "years; the freeze is the longest-running dated condition in this pack",
     "falsifier": "no measurable difference in the assets it is known to hold between freeze and "
                  "pre-freeze periods once the 2011 supply shock itself is controlled for",
     "notes": "REGISTERED, NOT HUNTED. The pack names this actor so that a Libyan sovereign-flow "
              "hypothesis is refused with a reason rather than invented"},
    {"name": "The Libyan joint ventures and Greenstream as the gas leg of an oil story",
     "jurisdiction": "ly",
     "holds": "the Mellitah complex and the Greenstream pipeline to Gela in Sicily, plus the "
              "Waha, Akakus and Mellitah field operations",
     "forced_to": ("stop when the fields stop: the same political triggers that close the oil "
                   "terminals interrupt the gas line",
                   "publish nothing directly, so the flow is visible only in Snam's table"),
     "when": "with the outages; and seasonally with Italian demand",
     "information": ("the field and pipeline state before the market sees the entry volume",),
     "constraints": ("declining Libyan gas production", "the same security environment as the "
                     "oil", "an Italian buyer with alternatives"),
     "instruments": ("XNGUSD", "XBRUSD", "EUSTX50"),
     "counterparties": ("the Italian buyer", "Snam as the receiving TSO", "the NOC"),
     "observables": ("the Snam Gela entry volume, daily",
                     "the force-majeure declarations that also touch gas",
                     "Italian import statistics by origin"),
     "impact": "a Libyan political event shows up in the EUROPEAN GAS BALANCE as well as in "
               "crude, on the same published Snam table as the Algerian volume -- which is why "
               "MGB-E and MGB-A share a control",
     "persistence": "days to weeks",
     "falsifier": "Libyan oil outages during which the Gela entry volume did not fall; if the "
                  "gas keeps flowing the event is an oil-terminal event and not a national one",
     "notes": "this actor is what stops the pack from treating Libya as a pure oil story and "
              "Algeria as a pure gas one"},
    # ---------------------------------------------------------------- Tunisia
    {"name": "The Tunisian state as the transit host of Algerian gas to Italy",
     "jurisdiction": "tn",
     "holds": "the Transtunisian pipeline corridor, the transit agreement with Algeria and "
              "Italy, and an IN-KIND ROYALTY on the volume that crosses",
     "forced_to": ("allow the transit under a long-term agreement",
                   "take part of its own gas supply as the royalty, which ties its domestic "
                   "energy balance to somebody else's export volume"),
     "when": "continuously; the royalty is struck on the transited volume and the agreement is "
             "periodically renegotiated",
     "information": ("the transited volume in real time, before the Italian table publishes it",
                     "the state of the Tunisian section of the pipeline"),
     "constraints": ("a domestic energy deficit that the royalty partly covers",
                     "a fiscal position that cannot easily replace the royalty with purchases",
                     "no control over the Algerian export decision"),
     "instruments": ("XNGUSD", "EUSTX50", "FRA40"),
     "counterparties": ("Sonatrach", "the Italian buyer", "ETAP and Sergaz as the national "
                        "operators"),
     "observables": ("the Snam Mazara del Vallo entry volume as the downstream measure",
                     "Tunisian energy balance publications",
                     "the dated transit-agreement renewals"),
     "impact": "A TUNISIAN TRANSIT EVENT IS AN ITALIAN SUPPLY EVENT, and the reverse is also "
               "true: an Algerian export cut reduces the Tunisian royalty and widens the "
               "Tunisian energy deficit at the same moment",
     "persistence": "the agreement persists for years; an interruption persists for days",
     "falsifier": "Tunisian political and security episodes during which the Mazara entry volume "
                  "did not move; a transit risk that never manifests is a narrative",
     "notes": "the one channel in this pack that makes a small economy matter to a large market"},
    {"name": "The Tunisian olive growers and the Office National de l'Huile",
     "jurisdiction": "tn",
     "holds": "one of the largest olive plantations in the world and a bulk export position in "
              "olive oil",
     "forced_to": ("harvest on the calendar the tree sets, from November",
                   "sell into a marketing season whose price is made in Spain",
                   "carry an ALTERNATE-BEARING crop that swings from year to year for biological "
                   "reasons as well as meteorological ones"),
     "when": "the campaign year, 1 November to 31 October; the crop is formed in the spring "
             "before it",
     "information": ("the crush volume as it happens, weeks before any balance is published",),
     "constraints": ("rainfall in the centre and south of the country",
                     "an EU tariff-rate quota that caps duty-free access to the largest market",
                     "bulk-export dependence, which means the price is taken and not made"),
     "instruments": ("SOYBEAN", "CORN", "E35"),
     "counterparties": ("the Italian and Spanish bulk buyers", "the ONH and the exporters",
                        "the European retail packers"),
     "observables": ("the ONAGRI campaign bulletins and the crush volume",
                     "the IOC balance and price series",
                     "Tunisian export tonnage by month",
                     "rainfall in the olive belt"),
     "impact": "a world supply variable in a commodity with no broker symbol; it routes into the "
               "vegetable-oil complex with the SPANISH CROP as the control",
     "persistence": "a campaign year, with the alternate-bearing cycle persisting two",
     "falsifier": "campaign outcomes that move the vegetable-oil complex only when the Spanish "
                  "crop moved in the same direction; that is a Spanish mechanism, not a Tunisian "
                  "one, and it is the first thing the domain tests",
     "notes": "the pack carries this because it is DATED, PUBLISHED AND WEATHER-DRIVEN, which is "
              "the shape a testable agricultural mechanism has"},
    {"name": "The Compagnie des Phosphates de Gafsa and the mining-basin labour actions",
     "jurisdiction": "tn",
     "holds": "the Gafsa phosphate basin, the rail link to the chemical complexes, and a "
              "world-scale share of traded phosphate rock",
     "forced_to": ("stop when the basin stops: sit-ins and road and rail blockades have halted "
                   "production repeatedly and for long periods",
                   "supply the Groupe Chimique Tunisien's DAP and TSP production before export"),
     "when": "the stoppages are dated and reported; they cluster around employment negotiations "
             "and local grievances rather than around price",
     "information": ("the state of the negotiation and the basin before production data appears",),
     "constraints": ("a workforce agreement that is politically fraught",
                     "a rail and port chain that a single blockade interrupts",
                     "a chemical complex that cannot run without the rock"),
     "instruments": ("WHEAT", "CORN", "SOYBEAN"),
     "counterparties": ("the Groupe Chimique Tunisien", "the export buyers",
                        "the UGTT and the local committees"),
     "observables": ("CPG and GCT production and export tonnage",
                     "the dated stoppage and restart reports in the Tunisian press",
                     "the fertiliser trade statistics"),
     "impact": "a fertiliser INPUT-COST channel into the northern-hemisphere planting decision: "
               "a farmer who cannot afford phosphate plants fewer acres or switches crop",
     "persistence": "weeks to months per stoppage; the structural decline persists for years",
     "falsifier": "stoppage windows in which Moroccan OCP output rose to offset them; if the "
                  "world balance did not change, the Tunisian stoppage is a local event and the "
                  "sibling `ma` pack holds the offsetting half",
     "notes": "THE PRICE ASSESSMENT IS PAYWALLED (NO_LAWFUL_GROUND), so the measurement is "
              "tonnage and dates against the crops, exactly as `ma` does for OCP"},
    {"name": "The Banque Centrale de Tunisie under capital control",
     "jurisdiction": "tn",
     "holds": "the daily reference rate, the reserve position measured in DAYS OF IMPORTS, and "
              "the exchange regulation that keeps the dinar non-convertible on the capital "
              "account",
     "forced_to": ("publish a reference rate every business day and reserves weekly",
                   "decide whether to finance the Treasury directly when external money is "
                   "unavailable"),
     "when": "scheduled board meetings and a weekly indicator release",
     "information": ("the reserve path and the import cover before the release",
                     "the Treasury's financing gap"),
     "constraints": ("a euro-dominated trade invoice",
                     "a tourism and remittance season that is the main hard-currency inflow",
                     "a political environment in which external programme money has been refused"),
     "instruments": ("EURUSD", "EURTRY", "E35"),
     "counterparties": ("the commercial banks", "the Treasury",
                        "the IMF and the bilateral lenders"),
     "observables": ("reserves in days of imports, weekly",
                     "the daily reference rate", "the policy rate decisions",
                     "the eurobond spread as the external market's answer"),
     "impact": "TUNISIA IS THE WITHIN-REGION CONTROL for the parallel-premium claims: same "
               "region, same language, same time zone, capital controls, and NO large organised "
               "parallel market -- so a premium effect that appears in Tunisia too is not a "
               "parallel-market effect",
     "persistence": "reserve episodes last quarters",
     "falsifier": "reserve-cover deterioration that produced no measurable move in the euro "
                  "crosses or the frontier-stress legs once the global risk cycle is partialled "
                  "out",
     "notes": "the reserves-in-days unit is the one the local market actually reads and it is "
              "published faster than any other macro number in this pack"},
    {"name": "The Tunisian sovereign borrower and the IMF programme that was agreed and refused",
     "jurisdiction": "tn",
     "holds": "a eurobond curve, a domestic debt stock and a subsidy bill that is the programme's "
              "central condition",
     "forced_to": ("roll maturities on a published calendar",
                   "decide publicly, and repeatedly, whether to accept a programme whose "
                   "conditions are politically unacceptable"),
     "when": "DATED DECISION POINTS: a staff-level agreement in October 2022 and a public "
             "political refusal in April 2023, with repeated returns to the question since",
     "information": ("the negotiation state before it is announced",
                     "the true subsidy and wage-bill trajectory"),
     "constraints": ("a subsidy and public-wage structure that is the condition",
                     "a maturity calendar that does not wait",
                     "bilateral and regional lenders as the alternative"),
     "instruments": ("EURTRY", "USDTRY", "EURUSD", "E35"),
     "counterparties": ("the IMF", "the eurobond holders", "the bilateral lenders",
                        "the domestic banks"),
     "observables": ("the dated staff-level agreement and refusal statements",
                     "the eurobond spread and the rating actions",
                     "the reserve path",
                     "the budget and its subsidy line"),
     "impact": "a live frontier sovereign-stress case with PUBLISHED DECISION DATES, which is "
               "the rarest thing in sovereign analysis: an event study with real event dates",
     "persistence": "quarters; the question has stayed open for years",
     "falsifier": "decision-date windows that are indistinguishable from matched windows in "
                  "other frontier sovereigns with no Tunisian news, on the same risk legs",
     "notes": "the executable leg is the frontier-stress crosses and the European indices; no "
              "Tunisian credit instrument is quoted by this broker"},
    # ---------------------------------------------------------------- Mauritania
    {"name": "SNIM and the Nouadhibou iron-ore train",
     "jurisdiction": "mr",
     "holds": "the Zouerate iron-ore deposits, the 700-kilometre mineral railway to Nouadhibou "
              "and the ore terminal there",
     "forced_to": ("ship on a monthly contracted lifting programme",
                   "sell into a seaborne market whose price is set in China",
                   "publish production and shipments because it borrows internationally"),
     "when": "monthly shipments; the annual report and the ANSADE trade bulletin",
     "information": ("its own tonnage and grade before the statistics publish it",
                     "the rail and terminal state"),
     "constraints": ("a single railway and a single port, so one interruption stops everything",
                     "ore grade and beneficiation economics against Australian and Brazilian "
                     "competitors",
                     "a Chinese demand cycle it has no influence over"),
     "instruments": ("USDCNH", "XALUSD", "XCUUSD"),
     "counterparties": ("the Chinese and European steel buyers", "the Mauritanian state as "
                        "majority owner", "the international lenders"),
     "observables": ("SNIM's published monthly production and shipments",
                     "CHINESE MIRROR CUSTOMS imports by origin",
                     "the Nouadhibou port call and loading record"),
     "impact": "a small but COUNTED share of seaborne iron ore, routed into the Chinese demand "
               "complex and the industrial metals with Australian and Brazilian shipments as the "
               "control that keeps a Mauritanian claim Mauritanian",
     "persistence": "monthly; an interruption persists as long as the railway is down",
     "falsifier": "months in which Mauritanian shipments fell and Australian and Brazilian "
                  "shipments did not; if the metals complex does not notice, the mechanism is a "
                  "Mauritanian fiscal story and not a world supply one",
     "notes": "the `au` and `cn` packs hold the two halves of this control and must be named in "
              "any test of it"},
    {"name": "The Banque Centrale de Mauritanie and the 2018 redenomination",
     "jurisdiction": "mr",
     "holds": "the ouguiya, the FX auction and the reserve position built on ore, gold, fish and "
              "now gas",
     "forced_to": ("run periodic FX auctions and publish a reference rate",
                   "manage a currency on a narrow and cyclical export base"),
     "when": "the auctions periodically; the redenomination was a single dated act on 2018-01-01",
     "information": ("the reserve and auction book", "the mining and fisheries receipts"),
     "constraints": ("an export base of four commodities",
                     "a small and partly informal financial system",
                     "a fiscal position that depends on SNIM and on fishing licence fees"),
     "instruments": ("USDCNH", "EURUSD", "XAUUSD"),
     "counterparties": ("the commercial banks at the auction", "SNIM and the mining companies",
                        "the fishing licence payers"),
     "observables": ("the auction results and the reference rate",
                     "the monetary statistics",
                     "the reserve path in the Article IV"),
     "impact": "small in world terms and decisive locally; the pack carries it mainly because "
               "the 2018 REDENOMINATION is the series break every Mauritanian level series hides",
     "persistence": "the redenomination is permanent; the rate path moves with the export cycle",
     "falsifier": "a Mauritanian macro series that shows the same behaviour before and after "
                  "2018-01-01 WITHOUT the 10:1 conversion applied is not measuring the economy, "
                  "it is measuring the break",
     "notes": "`mru_redenominate` exists because a ratio spliced across the break is SILENTLY "
              "right while a level is wrong by a factor of ten"},
    {"name": "The Greater Tortue Ahmeyim partners and the field Mauritania shares with Senegal",
     "jurisdiction": "mr",
     "holds": "an offshore gas field that STRADDLES THE MAURITANIA-SENEGAL MARITIME BOUNDARY and "
              "a floating LNG facility on it",
     "forced_to": ("split everything with Senegal under an intergovernmental cooperation "
                   "agreement, so neither state can act alone",
                   "announce capacity milestones publicly because the partners are listed "
                   "elsewhere and must disclose"),
     "when": "DATED MILESTONES: first gas in 2025 and a phased capacity ramp announced in "
             "advance; each slip is announced too",
     "information": ("the commissioning state of the facility before the market sees a cargo",),
     "constraints": ("a shared field that requires two governments to agree",
                     "an LNG market whose price is made at hubs neither country touches",
                     "a phased development whose later trains are not committed"),
     "instruments": ("XNGUSD", "XBRUSD", "EURUSD"),
     "counterparties": ("the Senegalese state and its national company",
                        "the international operators", "the LNG offtakers"),
     "observables": ("the dated milestone and first-cargo announcements",
                     "the Mauritanian and Senegalese ministries' releases",
                     "LNG cargo tracking in the trade press"),
     "impact": "a small but SCHEDULED addition to Atlantic LNG supply, with dates on it -- and "
               "it makes this pack and `west_africa` ONE PHYSICAL SYSTEM rather than two "
               "independent observations",
     "persistence": "the ramp persists for years; a slip persists for quarters",
     "falsifier": "GTA milestone announcements that carry no information for the gas legs once "
                  "US and Qatari LNG milestones in the same quarter are controlled for",
     "notes": "NEITHER PACK MAY CLAIM THIS FIELD ALONE; the interaction row with `west_africa` "
              "is the mechanism and not a courtesy"},
    {"name": "The Mauritanian fisheries ministry and the licensed EU and Chinese fleets",
     "jurisdiction": "mr",
     "holds": "one of the richest fishing grounds on earth and the licence regime over it",
     "forced_to": ("negotiate and publish a sustainable fisheries partnership agreement with the "
                   "European Union on a fixed multi-year cycle",
                   "license foreign fleets in a way that is itself a fiscal decision"),
     "when": "the EU agreement on its published renewal cycle; Chinese arrangements are less "
             "transparent and reach the record through trade statistics",
     "information": ("catch and licence data before publication",
                     "the state of the negotiation"),
     "constraints": ("a stock that can be overfished",
                     "a domestic processing sector that wants landings",
                     "a fiscal need for the licence fee"),
     "instruments": ("USDCNH", "EURUSD", "XAUUSD"),
     "counterparties": ("the European Union", "the Chinese distant-water fleet",
                        "the domestic processors at Nouadhibou"),
     "observables": ("the published EU partnership agreement and its financial contribution",
                     "CHINESE MIRROR CUSTOMS on cephalopods and other species",
                     "the port landing statistics"),
     "impact": "a real, published, dated external-revenue channel for a small state, and a "
               "second independent route into the Chinese demand leg alongside the iron ore",
     "persistence": "the agreements run for multiple years",
     "falsifier": "licence-cycle dates that carry no information for the Mauritanian external "
                  "position once the ore cycle is controlled for; if the ore explains it all, "
                  "the fishery is a fiscal detail and not a mechanism",
     "notes": "carried with its control named, exactly as the brief requires: the ore and the "
              "fish are two channels into one buyer and must not be double-counted"},
    # ---------------------------------------------------------------- shared
    {"name": "The European transmission system operators as the publishers of the truth",
     "jurisdiction": "shared",
     "holds": "the metering and the regulatory obligation to publish entry volumes at every "
              "interconnection point",
     "forced_to": ("publish physical flows daily under European transparency rules",
                   "publish them against the GAS DAY and not the calendar day"),
     "when": "each gas day, with roughly a one-day lag and a later metered settlement",
     "information": ("the metered volume before it is published",),
     "constraints": ("a regulated obligation they cannot decline",
                     "point definitions that change over time"),
     "instruments": ("XNGUSD", "EUSTX50", "NETH25", "E35"),
     "counterparties": ("the shippers", "the regulators", "ENTSOG as the aggregator"),
     "observables": ("the Snam and Enagas daily entry tables",
                     "the ENTSOG transparency API",
                     "the AGSI storage series that sets the state"),
     "impact": "THIS IS WHY THE PACK IS TESTABLE. The supplier is opaque and the receiver is "
               "transparent, so a Maghreb supply claim is checked against a number published by "
               "a European regulated monopoly that no Maghreb actor controls",
     "persistence": "permanent, as a regulatory obligation",
     "falsifier": "periods in which the published entry volume and the importing country's own "
                  "customs statistics disagree beyond metering tolerance; a disagreement is a "
                  "data-quality finding, not a market one, and it must be resolved before a cell",
     "notes": "the single most valuable actor in this pack is not in the Maghreb"},
    {"name": "OPEC's secondary sources as the only consistent production measurement",
     "jurisdiction": "shared",
     "holds": "a monthly production estimate for Algeria and Libya built from independent "
              "assessors rather than from the members' own statements",
     "forced_to": ("publish both the secondary-source estimate and the member's direct "
                   "communication, side by side, every month",),
     "when": "mid-month, on the MOMR calendar",
     "information": ("the assessors' underlying tanker and field data",),
     "constraints": ("an estimate, not a count", "revision in the following report",
                     "a membership that changes under the same table name"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "counterparties": ("the member states", "the assessors", "the market that reads the table"),
     "observables": ("the secondary-source column",
                     "the direct-communication column and the gap between them",
                     "the compliance tables for the quota-bound members"),
     "impact": "every Libyan and Algerian production claim in this pack is measured here; the "
               "GAP between the two columns is itself an observable about what a state wants "
               "believed",
     "persistence": "monthly, revised once",
     "falsifier": "months in which the two columns agreed and the market still moved on the "
                  "release; that is a global oil-balance reaction and not a Maghreb one",
     "notes": "ALGERIA IS QUOTA-BOUND AND LIBYA IS EXEMPT, which is the difference between an "
              "economic decision and an exogenous switch"},
)

# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "MGB-A", "title": "Algerian pipeline gas into Europe as a published daily flow",
     "jurisdiction": "dz",
     "objects": ("the Snam Mazara del Vallo daily entry volume (Transmed) and the Enagas Almeria "
                 "entry volume (Medgaz)",
                 "the declared route capacity, 33.5 plus 10.16 bcm/y after 2021",
                 "Algerian customs hydrocarbon export value by destination, as the price side",
                 "the Skikda and Arzew LNG loadings as the flexible leg"),
     "conditions": ("the European storage fill level on the day (AGSI)",
                    "whether the day falls inside the Algerian summer domestic peak",
                    "the declared route state from `pipeline_state` after 2021-10-31",
                    "whether Norwegian or LNG supply moved in the same window"),
     "instruments": ("XNGUSD", "EUSTX50", "NETH25", "E35", "EURUSD"),
     "controls": ("HENRY HUB AS THE CONTROL AND NEVER THE PROXY: an effect that appears in the "
                  "US benchmark too is a global gas effect and not an Algerian supply event",
                  "matched gas days with the same storage level and no Algerian flow change",
                  "Norwegian and LNG arrivals in the same window, partialled out",
                  "the Italian and Spanish demand side, so a flow fall caused by weak demand is "
                  "not read as a supply cut"),
     "notes": "A DAILY, OPEN, METERED SERIES carrying roughly a tenth of European gas supply, "
              "published by a European regulated monopoly that no Algerian actor controls. It is "
              "the best ground in this pack and the reason the pack exists"},
    {"id": "MGB-B", "title": "The 2021 Maghreb-Europe closure and the collapse of the third route",
     "jurisdiction": "dz",
     "objects": ("the transit contract that expired on 2021-10-31 and was not renewed",
                 "the Enagas Tarifa entry series going to zero, and later REVERSING to send "
                 "Spanish gas to Morocco",
                 "the Medgaz expansion completed in the same weeks",
                 "the June 2022 Spain-Algeria diplomatic rupture and its trade measures"),
     "conditions": ("before, across or after the 2021-11-01 closure",
                    "whether Spain's Algerian supply is single-route on the day",
                    "whether the window contains a dated diplomatic act between Algiers, Rabat "
                    "or Madrid"),
     "instruments": ("XNGUSD", "E35", "EURUSD", "FRA40"),
     "controls": ("the ITALIAN route over the same days, which was unaffected: a European gas "
                  "move that appears at Mazara as well is not an Iberian route event",
                  "matched windows with no diplomatic act",
                  "the `ma` pack's own Moroccan gas position, which is the other side of the "
                  "same closure and must be jointly controlled"),
     "notes": "A DATED, PUBLISHED, POLITICAL CAPACITY CUT of about 12 bcm/y, three months before "
              "the European gas shock of 2022. `pipeline_capacity('meg', day)` is 12.0 on "
              "2021-10-31 and 0.0 on 2021-11-01, which is the whole mechanism in two numbers"},
    {"id": "MGB-C", "title": "Algerian domestic gas demand as the binding constraint on export",
     "jurisdiction": "dz",
     "objects": ("the subsidised domestic tariff and the consumption growth it creates",
                 "the summer air-conditioning peak and the winter heating peak",
                 "the residual between Algerian production and Algerian export volume",
                 "CREG's and Sonelgaz's published regulatory and generation material"),
     "conditions": ("the season, and specifically whether the day falls in the summer peak",
                    "a northern-Algerian temperature anomaly on the day",
                    "the European injection season, which competes for the same molecule"),
     "instruments": ("XNGUSD", "EUSTX50", "XBRUSD"),
     "controls": ("Libyan Greenstream flow over the same days, which shares the weather and not "
                  "the Algerian demand structure",
                  "matched summer weeks with no temperature anomaly",
                  "European demand-side temperature, so an effect is not read backwards"),
     "notes": "PHYSICALLY CAUSAL AND SEASONAL AT ONCE: the molecules burned in Algiers are the "
              "molecules that do not arrive in Sicily, and the subsidy is why the constraint "
              "tightens every year"},
    {"id": "MGB-D", "title": "The dinar's two prices: the fixing and the Square Port Said premium",
     "jurisdiction": "dz",
     "objects": ("the Bank of Algeria daily interbank fixing",
                 "the reported parallel cash rate and its spread to the fixing",
                 "the import-licence and hard-currency allocation regime that creates the spread",
                 "the retail gold premium in the same market as the second store of value"),
     "conditions": ("the premium band from `dzd_parallel_premium` (NORMAL to EXTREME)",
                    "whether the window contains a dated import-restriction measure",
                    "the travel and religious season, which moves cash demand"),
     "instruments": ("EURUSD", "XAUUSD", "USDTRY"),
     "controls": ("TUNISIA over the same windows: capital controls, same region, same language, "
                  "NO large organised parallel market -- an effect that appears there too is not "
                  "a parallel-market effect",
                  "matched windows with no import measure",
                  "the oil price path, partialled out, because the premium follows revenue"),
     "notes": "THE SECOND LEG IS UNRELIABLE BY CONSTRUCTION and the domain says so: the premium "
              "is used as a SPREAD and never as a level, and no cell here can be compiled on the "
              "parallel rate alone"},
    {"id": "MGB-E", "title": "Libyan force majeure by terminal as an oil supply instrument",
     "jurisdiction": "ly",
     "objects": ("the NOC's dated declarations and liftings, named terminal by named terminal",
                 "Es Sider, Ras Lanuf, Zueitina, Brega and Hariga as separate switches",
                 "the OPEC secondary-source production series as the measured outcome",
                 "the five dated episodes in LIBYA_OUTAGES and their approximate sizes"),
     "conditions": ("whether the day is inside a declared episode (`libya_outage_state`)",
                    "how many named terminals the declaration covers",
                    "the OPEC+ policy state at the time, which sets the spare capacity that "
                    "absorbs it",
                    "whether the trigger was institutional (the 2024 governorship) or local"),
     "instruments": ("XBRUSD", "XTIUSD", "XNGUSD"),
     "controls": ("matched windows with the same OPEC+ state, the same dollar path and NO Libyan "
                  "declaration",
                  "declarations that were announced and not followed by a production fall, which "
                  "separate the headline from the barrel",
                  "Nigerian and Venezuelan outages in the same windows as the other exogenous "
                  "supply interruptions"),
     "notes": "AS CLOSE TO AN INSTRUMENTAL VARIABLE AS THIS MARKET OFFERS: about one per cent of "
              "world supply switching on published, dated, NON-ECONOMIC triggers, with the close "
              "announced as well as the open"},
    {"id": "MGB-F", "title": "The Libyan field shut-ins: Sharara, El Feel and the southern route",
     "jurisdiction": "ly",
     "objects": ("the repeated Sharara and El Feel closures and restarts",
                 "the pipeline from the southern fields to Zawiya, which is the single link",
                 "the local and armed actors who close them and the grievances they announce",
                 "the restart profile, which is slower than the shut-in"),
     "conditions": ("whether the shut-in is a FIELD event or a TERMINAL event",
                    "the announced duration against the realised one",
                    "whether a national political process was under way in the same window"),
     "instruments": ("XBRUSD", "XTIUSD", "EURUSD"),
     "controls": ("terminal-only episodes over the same period, which hold the country constant "
                  "and vary the mechanism",
                  "matched windows with a political process and no field closure",
                  "the restart windows, in which the same actors move the other way"),
     "notes": "THE WITHIN-COUNTRY CONTROL that makes MGB-E a mechanism rather than a headline: a "
              "shock that hits Es Sider and not Sharara is an eastern-terminal event and one "
              "that hits both is national"},
    {"id": "MGB-G", "title": "The Central Bank of Libya: two rate steps and a governorship that "
                             "is an oil variable",
     "jurisdiction": "ly",
     "objects": ("the 2020-12-16 unification at 4.48 and the 2024 devaluation",
                 "the 2014-2023 institutional split and the two publishers of one series",
                 "the letter-of-credit allocation as the transmission into the real economy",
                 "the August-October 2024 governorship dispute and the roughly 700 kb/d it "
                 "removed"),
     "conditions": ("the institutional era: split, unified, or contested",
                    "whether a governance episode coincided with a production interruption",
                    "the parallel-rate spread at the time"),
     "instruments": ("XBRUSD", "XAUUSD", "USDTRY"),
     "controls": ("CBL governance episodes that did NOT coincide with a production "
                  "interruption -- if crude moves on those too, the channel is sentiment",
                  "matched windows with the same oil price path and no Libyan institutional news",
                  "the Algerian and Tunisian currencies over the same windows as the "
                  "regional control"),
     "notes": "NO LIBYAN MACRO SERIES IS POOLED ACROSS 2014-2023 here, because for those years "
              "there was no single publisher and at times there were two different numbers"},
    {"id": "MGB-H", "title": "Tunisia as the transit state and the in-kind royalty on Italian gas",
     "jurisdiction": "tn",
     "objects": ("the Transtunisian corridor and the transit agreement",
                 "the IN-KIND ROYALTY, which ties Tunisia's own energy balance to Algeria's "
                 "export volume",
                 "the Snam Mazara entry volume as the downstream measure of the same pipe",
                 "the dated renegotiations of the transit terms"),
     "conditions": ("whether a Tunisian political or security episode is in the window",
                    "the Algerian export level, which sets the royalty",
                    "the Tunisian energy deficit state"),
     "instruments": ("XNGUSD", "EUSTX50", "FRA40"),
     "controls": ("the MEDGAZ route over the same days, which reaches Europe WITHOUT crossing "
                  "Tunisia: a flow event on both is Algerian, one on Transmed only is Tunisian",
                  "matched windows with no Tunisian episode",
                  "Italian demand, partialled out"),
     "notes": "THE CLEANEST TRANSIT CONTROL IN THE PACK, because the same exporter has TWO "
              "routes to Europe and only one of them crosses Tunisia"},
    {"id": "MGB-I", "title": "The Tunisian olive campaign as a dated, weather-driven world supply "
                             "series",
     "jurisdiction": "tn",
     "objects": ("the campaign year, 1 November to 31 October, and its phases",
                 "the ONAGRI crush volume and the export tonnage through the campaign",
                 "rainfall in the centre and south, which forms the crop in the spring before",
                 "the alternate-bearing cycle, which swings output for biological reasons"),
     "conditions": ("the campaign phase from `olive_campaign_year`",
                    "whether the Spanish crop moved in the same direction",
                    "the on-year or off-year position of the alternate-bearing cycle"),
     "instruments": ("SOYBEAN", "CORN", "E35"),
     "controls": ("THE SPANISH CROP, which is roughly half of world output: a price move that is "
                  "also a Spanish move is not a Tunisian mechanism",
                  "matched campaign phases in years with an average crop",
                  "the broader vegetable-oil complex, so a palm or soy shock is not attributed "
                  "to olives"),
     "notes": "OLIVE OIL IS NOT A BROKER SYMBOL, so the route is the vegetable-oil complex with "
              "the control named on the face of the domain; the campaign year and not the "
              "calendar year is the unit"},
    {"id": "MGB-J", "title": "Gafsa phosphate stoppages into the fertiliser cost of grain acreage",
     "jurisdiction": "tn",
     "objects": ("the dated CPG sit-ins, road and rail blockades and restarts",
                 "CPG and GCT production and export tonnage",
                 "the DAP and TSP output the rock feeds",
                 "the northern-hemisphere planting decision the fertiliser cost enters"),
     "conditions": ("whether a dated stoppage is in the window",
                    "whether Moroccan OCP output rose to offset it (the `ma` pack's half)",
                    "the planting season the window falls in"),
     "instruments": ("WHEAT", "CORN", "SOYBEAN"),
     "controls": ("MOROCCAN OCP OUTPUT over the same windows, which is the offsetting half of "
                  "world supply and is held by the sibling pack",
                  "matched stoppage-free windows in the same planting season",
                  "the energy cost of ammonia, which is the other half of the fertiliser price"),
     "notes": "THE ASSESSMENT IS PAYWALLED (NO_LAWFUL_GROUND), so this is measured on TONNAGE "
              "and DATES against the crops -- the same discipline `ma` applies to OCP, and the "
              "two packs must be mutually controlled or they double-count one world supply"},
    {"id": "MGB-K", "title": "Tunisian sovereign stress: a programme agreed and publicly refused",
     "jurisdiction": "tn",
     "objects": ("the October 2022 staff-level agreement and the April 2023 political refusal",
                 "the eurobond spread and the rating actions as the market's answer",
                 "reserves in DAYS OF IMPORTS, published weekly",
                 "the subsidy and wage bill that is the programme's condition"),
     "conditions": ("whether the window contains a dated programme decision point",
                    "the reserve-cover band at the time",
                    "the global frontier-risk cycle, which must be partialled out"),
     "instruments": ("EURTRY", "USDTRY", "EURUSD", "E35"),
     "controls": ("matched windows in other frontier sovereigns with no Tunisian news",
                  "the global risk cycle and the euro path, partialled out",
                  "reserve-cover deteriorations with no programme news, which separate the "
                  "fundamental from the announcement"),
     "notes": "AN EVENT STUDY WITH REAL EVENT DATES, which is rare in sovereign analysis; no "
              "Tunisian credit instrument is quoted, so the executable leg is the frontier "
              "crosses and the European indices"},
    {"id": "MGB-L", "title": "SNIM iron ore on the Nouadhibou train into the Chinese demand leg",
     "jurisdiction": "mr",
     "objects": ("monthly SNIM production and shipments",
                 "the single railway and the single ore terminal, which are one point of failure",
                 "CHINESE MIRROR CUSTOMS imports by origin as the independent measure",
                 "the ore grade and beneficiation economics against the big two exporters"),
     "conditions": ("whether Australian and Brazilian shipments moved in the same month",
                    "the Chinese steel demand state",
                    "whether a rail or terminal interruption is in the window"),
     "instruments": ("USDCNH", "XALUSD", "XCUUSD"),
     "controls": ("AUSTRALIAN AND BRAZILIAN SHIPMENTS in the same month, held by `au` and read "
                  "through `cn`: if the world balance did not change, the Mauritanian move is a "
                  "fiscal story and not a supply one",
                  "matched months with no Mauritanian interruption",
                  "the Chinese demand cycle itself, partialled out"),
     "notes": "THE INDEX IS LICENSED (NO_LAWFUL_GROUND), so the measurement is COUNTED TONNAGE "
              "on both sides of the trade -- the exporter's own file and the importer's customs"},
    {"id": "MGB-M", "title": "Greater Tortue Ahmeyim: a dated LNG ramp Mauritania shares with "
                             "Senegal",
     "jurisdiction": "mr",
     "objects": ("the announced phased capacity and the 2025 first gas",
                 "the milestone and slip announcements, each dated",
                 "the intergovernmental agreement that makes the field one system with Senegal",
                 "the cargo record as the delivered measure"),
     "conditions": ("the announced phase the window falls in",
                    "whether a US or Qatari LNG milestone landed in the same quarter",
                    "the European and Asian gas spread at the announcement"),
     "instruments": ("XNGUSD", "XBRUSD", "EURUSD"),
     "controls": ("US Gulf Coast and Qatari milestones in the same quarters, which separate "
                  "'world supply schedule' from 'Atlantic supply schedule'",
                  "matched quarters with no GTA announcement",
                  "the Senegalese side of the same field, held by `west_africa`, which must be "
                  "jointly controlled because it is the SAME MOLECULES"),
     "notes": "NEITHER PACK MAY CLAIM THIS FIELD ALONE. The interaction with `west_africa` is "
              "physical and not thematic: one reservoir, two flags, one capacity schedule"},
    {"id": "MGB-N", "title": "The Mauritanian fishery and the licensed EU and Chinese fleets",
     "jurisdiction": "mr",
     "objects": ("the published EU sustainable fisheries partnership agreement and its cycle",
                 "the Chinese distant-water fleet's presence, visible mainly in trade statistics",
                 "cephalopod and pelagic landings at Nouadhibou",
                 "the licence fee as an external revenue line"),
     "conditions": ("whether an agreement renewal or renegotiation is in the window",
                    "the ore cycle at the same time, which must be separated from it",
                    "the Chinese import cycle"),
     "instruments": ("USDCNH", "EURUSD", "XAUUSD"),
     "controls": ("THE ORE CYCLE, partialled out: if iron ore explains the whole external "
                  "position, the fishery is a fiscal detail and not a mechanism",
                  "matched windows with no licence event",
                  "the neighbouring West African fisheries agreements held by `west_africa`"),
     "notes": "carried with its control named, as the brief requires: ore and fish are two "
              "channels into ONE buyer and must not be double-counted"},
    {"id": "MGB-O", "title": "Four currencies, four regimes, one capital-control cluster",
     "jurisdiction": "shared",
     "objects": ("the DZD managed float with a reported parallel premium",
                 "the LYD's two dated steps and its own parallel market",
                 "the TND's managed rate behind capital controls with NO large parallel market",
                 "the MRU and the 2018-01-01 redenomination that breaks every level series"),
     "conditions": ("the regime of the currency in question",
                    "whether a parallel market exists for it at all",
                    "the commodity revenue state that funds the reserve position"),
     "instruments": ("EURUSD", "XAUUSD", "USDTRY", "EURTRY"),
     "controls": ("TUNISIA as the no-parallel-market control inside the same region",
                  "the `ma` dirham, a BASKET peg in the same neighbourhood, as the fourth regime",
                  "the oil and ore price paths, partialled out, because three of the four "
                  "reserve positions are commodity revenue"),
     "notes": "FOUR REGIMES IS THE POINT. A pooled 'Maghreb FX' study is measuring a managed "
              "float with a premium, a step-function peg, a controlled float with no premium and "
              "a redenominated currency, all at once, and calling the average a region"},
    {"id": "MGB-P", "title": "The EU's southern energy frontier: association councils, hydrogen "
                             "MOUs and pipelines that were never built",
     "jurisdiction": "shared",
     "objects": ("the dated EU association-council and trade decision points",
                 "the solar and green-hydrogen MOUs with Germany and Italy as forward supply "
                 "commitments with dates",
                 "the Trans-Saharan gas pipeline MOUs of 2009 and 2022, with zero delivered "
                 "capacity",
                 "GALSI, announced repeatedly and never built"),
     "conditions": ("whether the window contains a dated council or MOU signature",
                    "whether the announcement concerns capacity that was later delivered",
                    "the European energy-price state at the announcement"),
     "instruments": ("EURUSD", "GER40", "FRA40", "NETH25", "EUSTX50", "E35", "UK100"),
     "controls": ("GALSI AND THE TRANS-SAHARAN MOUs AS THE PLACEBO ARM: announcements with a "
                  "KNOWN OUTCOME of zero delivered capacity, which is the cleanest test of "
                  "whether announcement effects in European gas are real",
                  "matched windows with no announcement",
                  "the European energy price path itself, partialled out"),
     "notes": "AN ANNOUNCEMENT-EFFECT DOMAIN WITH A BUILT-IN NULL. Most announcement studies "
              "have no arm in which the announcement demonstrably delivered nothing; this ground "
              "has two, both decades long and both dated"},
)

#: (mechanism_family, horizon) per domain -- what the gauntlet needs to file a cell.
DOMAIN_CELL_SPEC: dict[str, tuple[str, str]] = {
    "MGB-A": ("physical_flow", "0-5 sessions"),
    "MGB-B": ("route_closure", "1-2 quarters"),
    "MGB-C": ("seasonal_constraint", "2-8 weeks"),
    "MGB-D": ("capital_control", "1-3 months"),
    "MGB-E": ("supply_instrument", "0-10 sessions"),
    "MGB-F": ("supply_instrument", "0-10 sessions"),
    "MGB-G": ("institutional_flow", "0-10 sessions"),
    "MGB-H": ("transit_risk", "0-5 sessions"),
    "MGB-I": ("harvest", "1-2 quarters"),
    "MGB-J": ("input_cost", "1-2 quarters"),
    "MGB-K": ("sovereign_stress", "0-10 sessions"),
    "MGB-L": ("export_volume", "1-3 months"),
    "MGB-M": ("supply_schedule", "1-4 quarters"),
    "MGB-N": ("licence_cycle", "1-2 quarters"),
    "MGB-O": ("fx_regime", "1-3 months"),
    "MGB-P": ("announcement", "1-2 quarters"),
}

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "mgb_pipeline_map", "domain_ids": ("MGB-A", "MGB-B", "MGB-H"), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.maghreb_energy.pack:mine_pipeline_map",
     "needs": ("PIPELINES", "SNAM:entry_mazara", "ENAGAS:entry_almeria", "XNGUSD D1 bars"),
     "notes": "emits the dated route map and the capacity total; the TSO series are named as "
              "requirements and reported UNMEASURED when the context does not carry them"},
    {"name": "mgb_libya_outages", "domain_ids": ("MGB-E", "MGB-F"), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.maghreb_energy.pack:mine_libya_outages",
     "needs": ("LIBYA_OUTAGES", "OPEC:mom_production", "XBRUSD, XTIUSD D1 bars"),
     "notes": "emits the five dated episodes with their named terminals and sizes; the matched "
              "no-declaration windows are the control the domain requires"},
    {"name": "mgb_currency_regimes", "domain_ids": ("MGB-D", "MGB-G", "MGB-O"),
     "kind": "mechanism", "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.maghreb_energy.pack:mine_currency_regimes",
     "needs": ("CURRENCIES", "BA:fixing", "the reported parallel rates (UNRELIABLE)",
               "EURUSD, XAUUSD D1 bars"),
     "notes": "emits the four regimes and the redenomination break; the parallel leg always "
              "carries its credibility label and is never emitted as a level"},
    {"name": "mgb_olive_campaign", "domain_ids": ("MGB-I",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.maghreb_energy.pack:mine_olive_campaign",
     "needs": ("ONAGRI:olive_campaign", "IOC:balance", "SOYBEAN, CORN D1 bars"),
     "notes": "emits the campaign year and its phase for the current date; the Spanish crop is "
              "named as the control and reported UNMEASURED when it is not carried"},
    {"name": "mgb_minerals_flows", "domain_ids": ("MGB-J", "MGB-L", "MGB-N"), "kind": "transfer",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.maghreb_energy.pack:mine_minerals_flows",
     "needs": ("SNIM:ore_shipments", "CPG:production", "Chinese mirror customs",
               "USDCNH, WHEAT D1 bars"),
     "notes": "emits the three mineral and fishery channels with their controls named; the "
              "licensed price assessments are declared absent rather than approximated"},
    {"name": "mgb_calendar_split", "domain_ids": ("MGB-C", "MGB-K"), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.maghreb_energy.pack:mine_calendar_split",
     "needs": ("WEEKEND_BY_JURISDICTION", "LUNAR_HOLIDAYS", "RAMADAN_WINDOWS"),
     "notes": "emits the SPLIT WORKING WEEK and the shared-session sample; a pooled Maghreb "
              "study that does not use this is aligning two different weeks"},
    {"name": "mgb_transmission_seeds",
     "domain_ids": ("MGB-A", "MGB-B", "MGB-E", "MGB-G", "MGB-L", "MGB-M", "MGB-P"),
     "kind": "transfer", "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.maghreb_energy.pack:mine_transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED",),
     "notes": "the pack's map as HYPOTHESIS discoveries, deduplicated by the registry"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("MGB-D", "MGB-G"),
    "release_surprise": ("MGB-A", "MGB-K"),
    "calendar_settlement": ("MGB-C", "MGB-I"),
    "holiday_liquidity": ("MGB-C", "MGB-O"),
    "positioning": ("MGB-K",),
    "carry_funding": ("MGB-K", "MGB-O"),
    "corporate_flow": ("MGB-A", "MGB-L"),
    "institutional_flow": ("MGB-G", "MGB-N"),
    "equity_mechanics": ("MGB-K",),
    "derivatives_expiry": ("MGB-A",),
    "failure": ("MGB-E", "MGB-F"),
    "residual": ("MGB-B", "MGB-P"),
    "transfer": ("MGB-H", "MGB-M"),
    "scouts": ("MGB-J", "MGB-N"),
    "session_microstructure": ("MGB-A", "MGB-H"),
}

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "MGB-E1", "source": "SNAM:entry_mazara (the daily Algerian volume into Sicily)",
     "target": "XNGUSD", "targets": ("XNGUSD", "EUSTX50"), "to_country": "global", "sign": "-",
     "mechanism": "a fall in the metered Algerian entry volume removes supply from the European "
                  "balance on the day it happens, and the fall is PUBLISHED by the receiving TSO "
                  "before any Algerian source comments on it",
     "horizon": "0 to 5 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "Sonatrach", "constraint": "domestic demand priority and field decline",
     "flow": "physical molecules out of the European balance",
     "condition": "a day with a material entry-volume change and no Norwegian or LNG offset",
     "control": "Henry Hub as the control and never the proxy; matched days with the same "
                "storage level; Norwegian and LNG arrivals partialled out",
     "falsifier": "entry-volume changes carry no XNGUSD or European index information once "
                  "storage, Norwegian supply, LNG arrivals and demand-side temperature are "
                  "controlled -- and any effect that also appears at Henry Hub is global",
     "evidence": "HYPOTHESIS"},
    {"id": "MGB-E2", "source": "The 2021-10-31 Maghreb-Europe transit expiry",
     "target": "XNGUSD", "targets": ("XNGUSD", "E35", "EURUSD"), "to_country": "global",
     "sign": "+",
     "mechanism": "about 12 bcm/y of route capacity was removed by a political decision and "
                  "Spain's Algerian supply became single-route, three months before the European "
                  "gas shock; the ROUTE STATE is a regime variable and not a signal",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the Algerian state", "constraint": "a transit contract it chose not to renew",
     "flow": "route capacity out of the Iberian supply map",
     "condition": "windows on either side of 2021-11-01 with the Italian route unchanged",
     "control": "the Italian route over the same days; the `ma` pack's Moroccan position; "
                "matched windows with no diplomatic act",
     "falsifier": "the Iberian hub premium to the Dutch hub shows no regime change across "
                  "2021-11-01 once the European gas shock of 2022 is excluded from the window",
     "evidence": "HYPOTHESIS"},
    {"id": "MGB-E3", "source": "Northern-Algerian summer temperature anomaly",
     "target": "XNGUSD", "targets": ("XNGUSD", "EUSTX50"), "to_country": "global", "sign": "-",
     "mechanism": "a subsidised, air-conditioning-driven domestic peak burns the molecules that "
                  "would otherwise be exported, so an Algerian heatwave is a European supply "
                  "event during the injection season",
     "horizon": "2 to 8 weeks", "horizon_class": "multi_day", "lag_days": 7.0,
     "actor": "Sonelgaz and the Algerian domestic customer",
     "constraint": "an administered tariff far below export parity",
     "flow": "export volume diverted to domestic burn",
     "condition": "a summer window with a measured northern-Algerian temperature anomaly",
     "control": "European demand-side temperature partialled out; Libyan Greenstream flow, which "
                "shares the weather and not the demand structure; matched summer weeks with no "
                "anomaly",
     "falsifier": "Algerian temperature anomalies carry no information for the Mazara entry "
                  "volume once European demand and maintenance schedules are controlled",
     "evidence": "HYPOTHESIS"},
    {"id": "MGB-E4", "source": "NOC:force_majeure declared on a named Libyan terminal",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD"), "to_country": "global", "sign": "+",
     "mechanism": "roughly one per cent of world supply is switched off by a POLITICAL, "
                  "non-economic trigger that is announced by name and by terminal, and switched "
                  "back on the same way",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the National Oil Corporation and the actors who close the fields",
     "constraint": "no control over the political trigger and an OPEC quota exemption",
     "flow": "barrels out of the seaborne balance",
     "condition": "a dated declaration covering at least one named terminal",
     "control": "matched windows with the same OPEC+ state and no declaration; declarations not "
                "followed by a production fall; Nigerian and Venezuelan outages in the same "
                "windows",
     "falsifier": "declaration windows are indistinguishable from matched no-declaration windows "
                  "on the crude legs once OPEC+ policy and the dollar path are partialled out",
     "evidence": "HYPOTHESIS"},
    {"id": "MGB-E5", "source": "The Libyan central-bank governorship dispute of August 2024",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD", "XAUUSD"), "to_country": "global",
     "sign": "+",
     "mechanism": "a MONETARY institution's leadership fight became an oil supply shock because "
                  "every Libyan export dollar passes through that balance sheet; roughly 700 "
                  "kb/d went offline for weeks",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the Central Bank of Libya and the two administrations",
     "constraint": "a single revenue gate with contested control",
     "flow": "barrels withheld as leverage in an institutional dispute",
     "condition": "a governance episode that coincides with a production interruption",
     "control": "CBL governance episodes with NO production interruption; matched windows with "
                "the same oil path and no Libyan institutional news",
     "falsifier": "governance episodes without an interruption move crude as much as those with "
                  "one, which would make the channel sentiment rather than supply",
     "evidence": "HYPOTHESIS"},
    {"id": "MGB-E6", "source": "A Tunisian transit episode on the Transtunisian corridor",
     "target": "XNGUSD", "targets": ("XNGUSD", "EUSTX50", "FRA40"), "to_country": "global",
     "sign": "+",
     "mechanism": "the Transmed crosses Tunisia and Medgaz does not, so an interruption that "
                  "appears at Mazara and NOT at Almeria is a transit event rather than an "
                  "Algerian export decision",
     "horizon": "0 to 5 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the Tunisian state, ETAP and Sergaz",
     "constraint": "a transit agreement with an in-kind royalty it depends on",
     "flow": "transit volume interrupted between producer and buyer",
     "condition": "a divergence between the two Algerian routes on the same gas day",
     "control": "the Medgaz route on the same days as the WITHIN-EXPORTER control; matched "
                "windows with no Tunisian episode; Italian demand partialled out",
     "falsifier": "route divergences carry no European gas information once maintenance "
                  "schedules and nominated capacity products are controlled for",
     "evidence": "HYPOTHESIS"},
    {"id": "MGB-E7", "source": "ONAGRI:olive_campaign crush and export tonnage",
     "target": "SOYBEAN", "targets": ("SOYBEAN", "CORN"), "to_country": "global", "sign": "-",
     "mechanism": "a top-three producer's campaign outcome is a world vegetable-oil supply "
                  "variable; with no olive-oil symbol quoted, the substitution runs through the "
                  "wider oilseed complex",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the Tunisian growers and the ONH",
     "constraint": "rainfall, the alternate-bearing cycle and an EU tariff-rate quota",
     "flow": "bulk oil into the European packing market",
     "condition": "a campaign whose outcome diverges from the Spanish crop's direction",
     "control": "THE SPANISH CROP, which is roughly half of world output; the palm and soy "
                "complex; matched campaign phases in average years",
     "falsifier": "Tunisian campaign outcomes move the oilseed complex only in the direction the "
                  "Spanish crop moved, which makes the mechanism Spanish",
     "evidence": "HYPOTHESIS"},
    {"id": "MGB-E8", "source": "CPG:production and the dated Gafsa stoppages",
     "target": "WHEAT", "targets": ("WHEAT", "CORN", "SOYBEAN"), "to_country": "global",
     "sign": "-",
     "mechanism": "a world-scale phosphate producer stopping on a DATED labour action raises the "
                  "fertiliser cost that enters the northern-hemisphere planting decision: fewer "
                  "acres, or a switch to the crop that needs less of it",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 60.0,
     "actor": "CPG, the Groupe Chimique Tunisien and the mining-basin committees",
     "constraint": "a single rail and port chain and a politically fraught workforce agreement",
     "flow": "rock and DAP out of the traded balance",
     "condition": "a stoppage window inside a planting season",
     "control": "MOROCCAN OCP OUTPUT over the same windows (the `ma` pack's half); the ammonia "
                "energy cost; matched stoppage-free windows in the same season",
     "falsifier": "stoppage windows in which OCP offset the loss show no acreage or price effect, "
                  "which makes the Tunisian stoppage a local event",
     "evidence": "HYPOTHESIS"},
    {"id": "MGB-E9", "source": "A dated Tunisian IMF-programme decision point",
     "target": "EURTRY", "targets": ("EURTRY", "USDTRY", "E35"), "to_country": "global",
     "sign": "+",
     "mechanism": "a frontier sovereign publicly accepting or refusing a programme reprices "
                  "frontier risk in the euro neighbourhood; the DATES are published, which is "
                  "what makes it an event study rather than a narrative",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the Tunisian state and the IMF",
     "constraint": "a subsidy and wage structure that is the programme's condition",
     "flow": "external financing on or off the table",
     "condition": "a dated staff-level agreement, refusal or review decision",
     "control": "matched windows in other frontier sovereigns with no Tunisian news; the global "
                "risk cycle and the euro path partialled out",
     "falsifier": "Tunisian decision dates are indistinguishable from matched frontier windows "
                  "with no Tunisian news on the same legs",
     "evidence": "HYPOTHESIS"},
    {"id": "MGB-E10", "source": "SNIM:ore_shipments and Chinese mirror customs by origin",
     "target": "USDCNH", "targets": ("USDCNH", "XALUSD", "XCUUSD"), "to_country": "global",
     "sign": "-",
     "mechanism": "a counted seaborne ore volume from a single-railway exporter enters the "
                  "Chinese steel input balance; the exporter publishes and the importer's "
                  "customs confirm, which is two independent measures of one flow",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 40.0,
     "actor": "SNIM", "constraint": "one railway, one terminal and an ore grade",
     "flow": "ore into the Chinese steel input balance",
     "condition": "a month in which Mauritanian shipments moved and the big two did not",
     "control": "AUSTRALIAN AND BRAZILIAN SHIPMENTS in the same month (`au`, `cn`); the Chinese "
                "demand cycle partialled out; matched months with no interruption",
     "falsifier": "Mauritanian shipment changes carry no information for the China leg or the "
                  "industrial metals once Australian and Brazilian volumes are controlled",
     "evidence": "HYPOTHESIS"},
    {"id": "MGB-E11", "source": "GTA:capacity_mtpa milestone and first-cargo announcements",
     "target": "XNGUSD", "targets": ("XNGUSD", "EURUSD"), "to_country": "global", "sign": "-",
     "mechanism": "a dated, phased addition to ATLANTIC LNG supply shared between two states; "
                  "the announcement, not the cargo, is the information, and a slip is an "
                  "announcement too",
     "horizon": "1 to 4 quarters", "horizon_class": "multi_day", "lag_days": 90.0,
     "actor": "the GTA partners and the two governments",
     "constraint": "a shared field requiring two governments and a phased commitment",
     "flow": "scheduled supply into the forward curve",
     "condition": "a milestone announcement with no US or Qatari milestone in the same quarter",
     "control": "US Gulf Coast and Qatari milestones in the same quarters; matched quarters with "
                "no GTA announcement; the Senegalese side held by `west_africa`",
     "falsifier": "GTA milestone quarters show no gas-curve information once US and Qatari "
                  "milestones in the same quarter are controlled for",
     "evidence": "HYPOTHESIS"},
    {"id": "MGB-E12", "source": "The Algerian parallel-market premium (`dzd_parallel_premium`)",
     "target": "EURUSD", "targets": ("EURUSD", "XAUUSD"), "to_country": "global", "sign": "+",
     "mechanism": "a widening cash premium is unmet hard-currency demand in a state whose "
                  "revenue is hydrocarbon exports, so it leads the import path a revenue shock "
                  "produces -- and it is the only near-real-time Algerian price of anything",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the importers and the cash changers",
     "constraint": "an allocation regime that rations hard currency",
     "flow": "hard-currency demand that the official allocation does not clear",
     "condition": "a premium band transition in `dzd_parallel_premium`",
     "control": "TUNISIA, same region and capital controls with no large parallel market; the "
                "oil price path partialled out; travel and religious seasons controlled",
     "falsifier": "the premium is indistinguishable from a seasonal travel pattern once Hajj, "
                  "summer diaspora travel and the school calendar are controlled for",
     "evidence": "HYPOTHESIS"},
    {"id": "MGB-E13", "source": "A dated EU-Maghreb association, energy or hydrogen MOU",
     "target": "EURUSD", "targets": ("EURUSD", "GER40", "FRA40", "E35"), "to_country": "global",
     "sign": "-",
     "mechanism": "forward supply commitments announced with dates change the expected European "
                  "energy cost path; the GALSI and Trans-Saharan histories are the arm in which "
                  "the announcement delivered nothing at all",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the European Commission, the member states and the Maghreb governments",
     "constraint": "an MOU is not capacity, and two decades of this ground prove it",
     "flow": "expected future supply into the forward curve",
     "condition": "a dated signature, split by whether capacity was later delivered",
     "control": "GALSI AND THE TRANS-SAHARAN MOUs AS THE PLACEBO ARM with a known zero outcome; "
                "matched windows with no announcement; the energy price path partialled out",
     "falsifier": "announcement windows that delivered capacity are indistinguishable from those "
                  "that delivered none, which would make the whole channel narrative",
     "evidence": "HYPOTHESIS"},
    {"id": "MGB-E14", "source": "The four currency regimes as one capital-control cluster",
     "target": "XAUUSD", "targets": ("XAUUSD", "EURUSD", "USDTRY"), "to_country": "global",
     "sign": "+",
     "mechanism": "where a currency is rationed, GOLD and cash foreign exchange are the household "
                  "store of value; a premium episode in two of the four at once is a regional "
                  "hard-currency scarcity signal rather than a national one",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the four central banks and the households facing them",
     "constraint": "convertibility restrictions of four different shapes",
     "flow": "household savings into gold and cash foreign currency",
     "condition": "simultaneous premium widening in Algeria and Libya",
     "control": "TUNISIA, which has the controls and not the parallel market; the `ma` dirham as "
                "a fourth regime; the global gold path partialled out",
     "falsifier": "joint premium episodes carry no gold information beyond what the dollar and "
                  "the real rate already carry",
     "evidence": "HYPOTHESIS"},
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "the Libyan civil war and the loss of a whole exporter", "start": "2011-02-17",
     "end": "2012-12-31",
     "regime": "Libyan production fell from about 1.6 mb/d to near zero and returned over the "
               "following year; the national accounts and the statistics bureau effectively "
               "stopped publishing and have never fully resumed",
     "markers": ("2011-02-17 the uprising begins", "2011-10-20 the end of the conflict phase",
                 "2012 the return toward pre-war output"),
     "why_it_matters": "THE START OF THE LIBYAN DATA VOID. No Libyan macro series is continuous "
                       "across this boundary, and MGB-G's institutional era begins here",
     "status": "SETTLED"},
    {"name": "the Libyan institutional split: two central banks, one currency",
     "start": "2014-09-01", "end": "2023-08-20",
     "regime": "the Central Bank of Libya was split between Tripoli and al-Bayda, with the two "
               "halves at times publishing different numbers for the same aggregate; the "
               "official and parallel rates diverged by a factor of three or four",
     "markers": ("2014 the split", "2020-12-16 the rate unification at 4.48",
                 "2023 the reunification of the institution"),
     "why_it_matters": "THERE IS NOT ONE LIBYAN MONETARY SERIES IN THIS WINDOW, there are two. "
                       "No Libyan macro series is pooled across it in this pack",
     "status": "SETTLED"},
    {"name": "the Libyan oil blockade of 2020", "start": "2020-01-18", "end": "2020-09-18",
     "regime": "the eastern terminals and the southern fields were closed together for eight "
               "months and national output fell to roughly 100 kb/d, removing about 1.1 mb/d "
               "from the seaborne balance through the COVID demand collapse",
     "markers": ("2020-01-18 the blockade begins", "2020-09-18 the reopening agreed",
                 "2020-04-20 WTI settles negative inside the same window"),
     "why_it_matters": "the largest dated Libyan supply event in the modern sample and the "
                       "hardest to identify, because it coincided with the largest demand shock "
                       "in the modern sample; any study of it must carry both",
     "status": "SETTLED"},
    {"name": "the Maghreb-Europe closure and the end of the three-route map",
     "start": "2021-11-01", "end": "2026-12-31",
     "regime": "Algeria did not renew the Moroccan transit contract that expired on 2021-10-31; "
               "about 12 bcm/y of route capacity left the map, Medgaz was expanded in the same "
               "weeks, and Spain's Algerian supply became single-route",
     "markers": ("2021-08-24 diplomatic relations with Morocco severed",
                 "2021-10-31 the transit contract expires", "2021-11-01 the line stops carrying "
                 "Algerian gas westward"),
     "why_it_matters": "MGB-B's whole state variable. `pipeline_capacity('meg', day)` is 12.0 on "
                       "one day and 0.0 on the next, and the `ma` pack holds the Moroccan side "
                       "of the same event",
     "status": "OPEN"},
    {"name": "the European gas shock and Algeria as Italy's largest supplier",
     "start": "2022-02-24", "end": "2023-12-31",
     "regime": "European gas repriced by an order of magnitude and decoupled from the US "
               "benchmark; Italy signed supply agreements with Sonatrach in April and July 2022 "
               "and Algeria became its largest pipeline supplier, while the Spain-Algeria "
               "relationship ruptured in June 2022",
     "markers": ("2022-04-11 the first Italy-Sonatrach agreement",
                 "2022-07-18 the second Italy-Sonatrach agreement",
                 "2022-06-08 the Spanish diplomatic rupture and its trade measures"),
     "why_it_matters": "THE ERA IN WHICH HENRY HUB STOPPED BEING A PROXY FOR ANYTHING EUROPEAN. "
                       "A study that pools this window with the years before it, using the US "
                       "benchmark, is measuring the LNG arbitrage and calling it a supply shock",
     "status": "SETTLED"},
    {"name": "the Algerian unconventional-financing episode", "start": "2017-10-01",
     "end": "2019-12-31",
     "regime": "the Bank of Algeria was authorised to finance the Treasury directly after the "
               "oil-price collapse; the facility was used heavily and then wound down, with a "
               "measurable consequence for the money stock and the parallel premium",
     "markers": ("2017 the enabling law", "2019 the wind-down"),
     "why_it_matters": "a DATED MONETARY REGIME with a start, an end and a transmission into the "
                       "premium MGB-D measures; pooling it with the years around it averages two "
                       "different monetary standards",
     "status": "SETTLED"},
    {"name": "the Mauritanian redenomination", "start": "2018-01-01", "end": "2018-12-31",
     "regime": "one new ouguiya (MRU) replaced ten old ones (MRO); every level series in "
               "Mauritanian currency changes by a factor of ten at this boundary while every "
               "ratio series is unchanged",
     "markers": ("2018-01-01 MRU replaces MRO at 1:10",),
     "why_it_matters": "THE MOST DANGEROUS SERIES BREAK IN THIS PACK, because the error survives "
                       "every sanity check that looks at growth rates; `mru_redenominate` exists "
                       "to apply it and never to infer it",
     "status": "SETTLED"},
    {"name": "the Tunisian programme era: agreed at staff level and publicly refused",
     "start": "2022-10-15", "end": "2026-12-31",
     "regime": "a staff-level agreement was reached in October 2022 and publicly refused at the "
               "political level in April 2023; the question has reopened repeatedly since, with "
               "bilateral and regional money as the alternative and the subsidy bill as the "
               "condition",
     "markers": ("2022-10 the staff-level agreement", "2023-04 the public political refusal",
                 "the subsequent maturity rolls met without a programme"),
     "why_it_matters": "MGB-K's event dates. A frontier sovereign with PUBLISHED decision points "
                       "is the rarest thing in sovereign analysis, and the refusals are as "
                       "dated as the agreements",
     "status": "OPEN"},
    {"name": "the Atlantic LNG ramp and the current Maghreb supply regime", "start": "2024-01-01",
     "end": "2026-12-31",
     "regime": "Greater Tortue Ahmeyim reached first gas in 2025 on a phased schedule shared "
               "with Senegal; Libya's output continues to switch on and off on institutional "
               "triggers, the 2024 CBL dispute being the clearest case; Algeria's export is "
               "increasingly constrained by its own domestic demand",
     "markers": ("2024-08-26 the CBL governorship dispute begins",
                 "2024 the Libyan dinar devaluation", "2025 GTA first gas"),
     "why_it_matters": "the CURRENT regime, in which every cell this pack mints today sits: a "
                       "scheduled Atlantic supply addition meeting an unscheduled Libyan switch "
                       "and a structurally tightening Algerian export",
     "status": "OPEN"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "LIBYA HAS TWO COMPETING ADMINISTRATIONS AND LIBYAN ENTITIES HAVE BEEN "
                   "SUBJECT TO UN AND NATIONAL MEASURES",
     "measured": "the Security Council 1970 sanctions regime, its Panel of Experts reports and "
                 "the asset freeze on the Libyan Investment Authority are all PUBLIC documents",
     "consequence": "NOTHING IN THIS PACK TOUCHES ANY ENTITY'S PRIVATE SYSTEMS AND NOTHING "
                    "BYPASSES AN ACCESS CONTROL. Everything used here is public: NOC and "
                    "Sonatrach announcements, OPEC's Monthly Oil Market Report, IEA and EIA "
                    "releases, the Italian and Spanish TSOs' published flow data, ENTSOG's "
                    "transparency platform, national statistics and central-bank publications, "
                    "UN Panel of Experts reports and the public press. The desk executes ONLY "
                    "broker symbols and never a Maghreb instrument"},
    {"constraint": "none of the four currencies is quoted by this broker",
     "measured": "data/universe/universe.json holds no DZD, LYD, TND or MRU symbol in any pairing",
     "consequence": "every domestic mechanism terminates in gas, crude, gold, the industrial "
                    "metals, the grains, the euro, the European indices or the frontier-stress "
                    "crosses; the four currencies are INPUTS and never cells"},
    {"constraint": "the European gas hubs are not Fusion symbols",
     "measured": "TTF, PSV and PVB appear nowhere in the broker registry",
     "consequence": "XNGUSD is the executable leg, the TSOs' PUBLISHED PHYSICAL FLOWS are the "
                    "European observable, and HENRY HUB IS A CONTROL AND NOT A PROXY -- the two "
                    "benchmarks decoupled by an order of magnitude in 2022 and a study that "
                    "substituted one for the other measured the LNG arbitrage"},
    {"constraint": "the crude differentials, the LNG markers, the fertiliser and the iron-ore "
                   "assessments all forbid machine extraction",
     "measured": "Argus, Platts, ICIS, CRU and Profercy terms; registered "
                 "machine_use_allowed=false",
     "consequence": "MGB-E, MGB-J and MGB-L are measured on COUNTED PHYSICAL VOLUMES on both "
                    "sides of each trade -- the exporter's file and the importer's customs -- "
                    "and the absent price is named rather than approximated"},
    {"constraint": "the Algerian and Libyan official web pages OVERWRITE IN PLACE",
     "measured": "the Bank of Algeria fixing table, the CBL rate page and the NOC production "
                 "page all publish TODAY and keep no history",
     "consequence": "the point-in-time history of three of this pack's series exists only in the "
                    "archive layer's crawls; a cell compiled on an un-archived month is "
                    "UNMEASURED rather than assumed, which is why those datasets carry "
                    "pit_feasible=false"},
    {"constraint": "the Algerian parallel rate is published by no authority",
     "measured": "it reaches the desk only through the press and private trackers whose sampling "
                 "is unknown",
     "consequence": "`dzd_parallel_premium` attaches an UNRELIABLE credibility label to every "
                    "answer, the premium is used only as a SPREAD, and no cell in this pack is "
                    "compiled on the parallel rate as a level"},
    {"constraint": "the Islamic-calendar feasts are announcements and not calculations, and the "
                   "working week is SPLIT across the four states",
     "measured": "LUNAR_HOLIDAYS is typed for 2024-2026 with each row naming all four sighting "
                 "authorities, 2026 is PROJECTED throughout, and WEEKEND_BY_JURISDICTION records "
                 "that Tunisia rests Saturday-Sunday while the other three rest Friday-Saturday",
     "consequence": "a pooled Maghreb session study must use `shared_session_days`, which is a "
                    "much smaller sample than a weekday filter suggests, and any cell that "
                    "depends on a 2026 feast date carries the PROJECTED label"},
    {"constraint": "Libya has no securities tape and Mauritania has no exchange at all",
     "measured": "no index symbol for either appears in the broker registry, and neither country "
                 "publishes a continuous local price series",
     "consequence": "every Libyan and Mauritanian mechanism terminates in a commodity, in gold "
                    "or in the dollar; the local equity leg is UNMEASURED by name and never "
                    "proxied by a regional index"},
    {"constraint": "Morocco's phosphate and Morocco's gas position are held by the `ma` pack",
     "measured": "OCP is the offsetting half of world phosphate supply and the Maghreb-Europe "
                 "closure is the other half of Morocco's gas story",
     "consequence": "`ma` and this pack are NOT independent observations on either mechanism and "
                    "must be mutually controlled in any cross-country test, or one world supply "
                    "is counted twice"},
)

INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "Snam daily entry-point physical flows at Mazara del Vallo and Gela",
    "Enagas daily entry volumes at Almeria and Tarifa",
    "ENTSOG transparency platform physical flows and nominations",
    "AGSI European gas storage fill levels",
    "OPEC MOMR secondary-source crude production for Algeria and Libya",
    "SNIM monthly iron-ore production and shipments",
    "Chinese and European mirror customs by origin (UN Comtrade)",
    "Bourse de Tunis monthly foreign-participation statistics",
)
SERIES: dict[str, str] = {
    "MGB_TRANSMED": "SNAM:entry_mazara", "MGB_GREENSTREAM": "SNAM:entry_gela",
    "MGB_MEDGAZ": "ENAGAS:entry_almeria", "MGB_TARIFA": "ENAGAS:entry_tarifa",
    "MGB_ENTSOG": "ENTSOG:physical_flow", "MGB_STORAGE": "AGSI:fill_level",
    "MGB_LY_PRODUCTION": "OPEC:mom_production", "MGB_NOC_FM": "NOC:force_majeure",
    "MGB_DZ_FIX": "BA:fixing", "MGB_DZ_PARALLEL": "TRACKERS:square_rate",
    "MGB_LY_RATE": "CBL:official_rate", "MGB_TN_RESERVES": "BCT:reserves_days",
    "MGB_TN_REFERENCE": "BCT:reference_rate", "MGB_OLIVE": "ONAGRI:olive_campaign",
    "MGB_PHOSPHATE": "CPG:production", "MGB_ORE": "SNIM:ore_shipments",
    "MGB_GTA": "GTA:capacity_mtpa", "MGB_MIRROR_CN": "COMTRADE:cn_imports_by_origin",
}

#: OTHER COUNTRY PACKS THIS ONE HAS A MEASURABLE INTERACTION WITH. This is how the desk stops
#: testing each country in isolation: a row here says WHICH other pack's observable must be
#: partialled out before this pack's claim is its own.
INTERACTIONS: tuple[dict[str, Any], ...] = (
    {"with": "ma", "mechanism": "THE MAGHREB-EUROPE PIPELINE IS LITERALLY THE INTERACTION. The "
                                "line ran from Hassi R'Mel THROUGH MOROCCO to Tarifa and was "
                                "SHUT on 2021-10-31 when Algeria did not renew the transit "
                                "contract in the rupture with Rabat; the same act removed "
                                "Morocco's Algerian gas and made Spain's supply single-route. "
                                "The two packs also hold the two halves of world phosphate (OCP "
                                "and CPG) and share the Hijri calendar",
     "observable": "the Enagas Tarifa entry series, which goes to zero and later REVERSES to "
                   "send Spanish gas into Morocco; OCP's output against CPG's; Morocco's "
                   "announced Eid dates, which have landed a day after the Maghreb's",
     "targets": ("XNGUSD", "E35", "WHEAT", "CORN"),
     "control": "the Italian route over the same days separates 'Algerian export' from 'Iberian "
                "route'; OCP output is the offsetting half of any Gafsa stoppage claim and the "
                "two packs must be mutually controlled or one world supply is counted twice; "
                "Morocco's own announced feast dates are the out-of-pack seasonal control"},
    {"with": "west_africa", "mechanism": "GREATER TORTUE AHMEYIM STRADDLES THE "
                                         "MAURITANIA-SENEGAL MARITIME BOUNDARY, so the two "
                                         "packs are ONE PHYSICAL SYSTEM: one reservoir, two "
                                         "flags, one phased capacity schedule governed by an "
                                         "intergovernmental agreement neither state can act "
                                         "outside of",
     "observable": "the shared GTA milestone and first-cargo announcements, and the two "
                   "countries' fisheries agreements with the same European and Chinese fleets",
     "targets": ("XNGUSD", "XBRUSD", "EURUSD", "USDCNH"),
     "control": "NEITHER PACK MAY CLAIM A GTA MILESTONE ALONE; every GTA cell must carry the "
                "Senegalese side, and a West African fisheries claim must be partialled out of "
                "any Mauritanian licence claim"},
    {"with": "eg", "mechanism": "Egypt is the other North African gas exporter to Europe and its "
                                "Idku and Damietta LNG trains compete for the same European "
                                "demand; an Egyptian export swing and an Algerian pipeline "
                                "swing are substitutes in the same balance",
     "observable": "Egyptian LNG export cargoes and the Egyptian domestic-demand seasonality "
                   "that has repeatedly halted them",
     "targets": ("XNGUSD", "EUSTX50"),
     "control": "partial out Egyptian LNG availability before an Algerian supply claim is called "
                "Algerian; both countries divert export molecules to domestic summer demand, so "
                "the seasonal channel is shared and must be separated"},
    {"with": "opec_north", "mechanism": "Iraq and Iran are the other OPEC producers whose output "
                                        "moves on non-price political triggers, so they are the "
                                        "natural control arm for the Libyan supply instrument",
     "observable": "dated Iraqi and Iranian export interruptions and sanctions decisions",
     "targets": ("XBRUSD", "XTIUSD"),
     "control": "matched windows in which another OPEC producer's output moved on a political "
                "trigger and Libya's did not; if crude responds identically, the mechanism is "
                "'political supply risk' and not Libyan"},
    {"with": "sa", "mechanism": "Saudi spare capacity is what absorbs a Libyan outage, so the "
                                "PRICE EFFECT of any Libyan shut-in is conditional on the Saudi "
                                "and OPEC+ policy state at the time",
     "observable": "OPEC+ quota decisions, Saudi voluntary cuts and the estimated spare capacity",
     "targets": ("XBRUSD", "XTIUSD"),
     "control": "condition every MGB-E cell on the OPEC+ state; an outage into abundant spare "
                "capacity and one into a tight market are two different experiments"},
    {"with": "cn", "mechanism": "China is the buyer of Mauritanian iron ore and of much of its "
                                "cephalopod catch, so both Mauritanian export channels arrive "
                                "through one demand cycle and must not be double-counted",
     "observable": "Chinese customs imports by origin for iron ore and molluscs; the Chinese "
                   "steel cycle",
     "targets": ("USDCNH", "XALUSD", "XCUUSD"),
     "control": "partial out the Chinese demand cycle before a Mauritanian export claim is "
                "attributed to Mauritanian supply; the mirror customs are the independent "
                "measure of the same flow"},
    {"with": "au", "mechanism": "Australia is the marginal seaborne iron-ore supplier, so "
                                "Australian shipments are the control that decides whether a "
                                "Mauritanian shipment change is a world supply event at all",
     "observable": "Australian monthly iron-ore export volumes and the Pilbara loading rate",
     "targets": ("USDCNH", "XALUSD"),
     "control": "months in which Mauritanian shipments fell and Australian shipments did not; if "
                "the complex does not notice, the mechanism is Mauritanian fiscal and not world "
                "supply"},
    {"with": "tr", "mechanism": "the lira is the executable Mediterranean frontier-stress leg "
                                "this pack routes Tunisian sovereign events into, and Turkey is "
                                "also a growing buyer of Algerian gas under long-term contract",
     "observable": "dated Turkish policy events, and the Turkish LNG and pipeline offtake from "
                   "Algeria",
     "targets": ("USDTRY", "EURTRY"),
     "control": "exclude windows containing a Turkish domestic policy event, or a Tunisian "
                "sovereign signal is measuring Ankara"},
    {"with": "gulf", "mechanism": "the Gulf pack holds the Qatari LNG capacity schedule, which "
                                  "is the largest scheduled addition to world LNG supply and "
                                  "therefore the competing supply arm for every Algerian and "
                                  "GTA gas claim; the two packs also share the Hijri calendar",
     "observable": "the announced North Field capacity steps and Qatari SPA signatures",
     "targets": ("XNGUSD", "XBRUSD", "XAUUSD"),
     "control": "Qatari milestones in the same quarter must be partialled out of any GTA or "
                "Algerian supply-schedule claim; a gas move that follows a Qatari announcement "
                "is not a Maghreb event"},
    {"with": "ng", "mechanism": "Nigeria is the third party to the Trans-Saharan gas pipeline "
                                "MOUs and the other large African LNG exporter, so the "
                                "announcement arm of MGB-P is shared with it and Nigerian "
                                "outages are a control for the Libyan supply instrument",
     "observable": "the dated Trans-Saharan MOUs and Nigerian LNG force-majeure declarations",
     "targets": ("XNGUSD", "XBRUSD"),
     "control": "Nigerian outages in the same windows as the other exogenous African supply "
                "interruption; a Trans-Saharan announcement effect must be measured on both "
                "signatories or it belongs to neither"},
)

# --------------------------------------------------------------------------- the testable cells
def cells() -> tuple[dict[str, Any], ...]:
    """Every testable cell this pack mints: domain x its own instruments x its own conditions.

    Each row is what the gauntlet needs to compile one test -- the symbol, the condition that
    gates it, the mechanism family it is filed under, the horizon, and the FIRST negative control
    the domain declared, so a cell can never travel without one. A cell whose condition this
    pack's own data plane cannot evaluate is not minted, which is why the count is in the low
    hundreds rather than in the thousands.
    """
    out: list[dict[str, Any]] = []
    for dom in DOMAINS:
        did = str(dom["id"])
        family, horizon = DOMAIN_CELL_SPEC.get(did, ("residual", "0-10 sessions"))
        controls = tuple(dom["controls"])
        for sym in dom["instruments"]:
            for i, cond in enumerate(dom["conditions"]):
                out.append({
                    "cell_id": f"{CODE}:{did}:{sym}:c{i}",
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


def mine_pipeline_map(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The dated Maghreb-Europe route map and its capacity total (MGB-A, MGB-B, MGB-H)."""
    today = datetime.now(tz=UTC).date()
    rows = [pipeline_state(key, today) for key in sorted(PIPELINES)]
    emitted = sum(1 for r in rows
                  if _emit(ctx, "mgb_pipeline",
                           f"{r['pipeline']}: {r['state']} at {r['capacity_bcm']} bcm/y "
                           f"-> {r['lands_in']}"))
    return {"miner": "mgb_pipeline_map", "rows": rows, "emitted": emitted,
            "capacity_bcm_today": maghreb_export_capacity(today),
            "capacity_bcm_before_closure": maghreb_export_capacity(date(2021, 10, 31)),
            "unmeasured": ["SNAM:entry_mazara and ENAGAS:entry_almeria are not on this tree, so "
                           "no flow is measured here; the route map is the state variable and "
                           "the TSO series are the measurement the context must feed"],
            "targets": ("XNGUSD", "EUSTX50", "E35", "EURUSD")}


def mine_libya_outages(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The five dated Libyan episodes with their named terminals and sizes (MGB-E, MGB-F)."""
    rows: list[dict[str, Any]] = [
        {"start": s.isoformat(), "end": e.isoformat(), "what": what,
         "where": tuple(where), "kb_d_offline": kbd, "status": st}
        for s, e, what, where, kbd, st in LIBYA_OUTAGES]
    emitted = sum(1 for r in rows
                  if _emit(ctx, "mgb_libya_outage",
                           f"{r['start']}..{r['end']}: {r['kb_d_offline']} kb/d offline at "
                           f"{', '.join(str(w) for w in r['where'])} [{r['status']}]"))
    return {"miner": "mgb_libya_outages", "rows": rows, "emitted": emitted,
            "terminals": LIBYAN_TERMINALS, "fields": LIBYAN_FIELDS,
            "unmeasured": ["OPEC:mom_production is not carried here, so the realised size of "
                           "each episode is the pack's declared approximation and not a "
                           "measurement; the matched no-declaration control windows are named "
                           "and not built"],
            "targets": ("XBRUSD", "XTIUSD", "XNGUSD")}


def mine_currency_regimes(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The four regimes, the redenomination break and the premium machinery (MGB-D/G/O)."""
    rows = [{"currency": c, "jurisdiction": str(v["jurisdiction"]), "regime": str(v["regime"]),
             "since": str(v["since"]), "parallel_market": bool(v["parallel_market"])}
            for c, v in CURRENCIES.items()]
    break_row = mru_redenominate(1000.0, date(2017, 6, 1))
    emitted = sum(1 for r in rows
                  if _emit(ctx, "mgb_currency",
                           f"{r['currency']} ({r['jurisdiction']}): {r['regime']} since "
                           f"{r['since']}, parallel market={r['parallel_market']}"))
    return {"miner": "mgb_currency_regimes", "rows": rows, "emitted": emitted,
            "redenomination_check": break_row,
            "unmeasured": ["no fixing series and no parallel-rate series is on this tree, so no "
                           "premium is computed here; `dzd_parallel_premium` is the estimator "
                           "the context must feed, and its second leg is UNRELIABLE by "
                           "construction"],
            "targets": ("EURUSD", "XAUUSD", "USDTRY", "EURTRY")}


def mine_olive_campaign(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The Tunisian olive campaign year and phase for the current date (MGB-I)."""
    today = datetime.now(tz=UTC).date()
    rows = [olive_campaign_year(today),
            olive_campaign_year(date(today.year, 11, 15)),
            olive_campaign_year(date(today.year, 4, 15))]
    emitted = sum(1 for r in rows
                  if _emit(ctx, "mgb_olive",
                           f"campaign {r['campaign']} ({r['start']}..{r['end']}): {r['phase']}"))
    return {"miner": "mgb_olive_campaign", "rows": rows, "emitted": emitted,
            "unmeasured": ["ONAGRI:olive_campaign and the IOC balance are not carried here; the "
                           "SPANISH CROP is the control and it is named rather than measured"],
            "targets": ("SOYBEAN", "CORN", "E35")}


def mine_minerals_flows(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The phosphate, iron-ore and fishery channels with their controls named (MGB-J/L/N)."""
    rows = [
        {"channel": "phosphate", "jurisdiction": "tn", "series": SERIES["MGB_PHOSPHATE"],
         "targets": ("WHEAT", "CORN", "SOYBEAN"),
         "control": "Moroccan OCP output over the same windows (`ma`)"},
        {"channel": "iron_ore", "jurisdiction": "mr", "series": SERIES["MGB_ORE"],
         "targets": ("USDCNH", "XALUSD", "XCUUSD"),
         "control": "Australian and Brazilian shipments in the same month (`au`, `cn`)"},
        {"channel": "fishery", "jurisdiction": "mr", "series": SERIES["MGB_MIRROR_CN"],
         "targets": ("USDCNH", "EURUSD"),
         "control": "the ore cycle partialled out, so one buyer is not counted twice"},
    ]
    emitted = sum(1 for r in rows
                  if _emit(ctx, "mgb_minerals",
                           f"{r['channel']} ({r['jurisdiction']}) -> "
                           f"{', '.join(r['targets'])}; control: {r['control']}"))
    return {"miner": "mgb_minerals_flows", "rows": rows, "emitted": emitted,
            "unmeasured": ["the phosphate, iron-ore and olive price assessments are all LICENSED "
                           "and registered machine_use_allowed=false; the measurement is counted "
                           "tonnage on both sides of each trade and neither side is on this tree"],
            "targets": ("WHEAT", "CORN", "SOYBEAN", "USDCNH", "XALUSD", "XCUUSD")}


def mine_calendar_split(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The split working week and the shared-session sample (MGB-C, MGB-K)."""
    rows = [{"jurisdiction": cc, "weekend": weekend_weekdays(cc),
             "holidays_2025": len(holidays_for(cc, 2025))} for cc in JURISDICTIONS]
    shared = shared_session_days(date(2025, 3, 1), date(2025, 3, 31))
    emitted = sum(1 for r in rows
                  if _emit(ctx, "mgb_calendar",
                           f"{r['jurisdiction']}: weekend={r['weekend']}, "
                           f"{r['holidays_2025']} statutory closures in 2025"))
    return {"miner": "mgb_calendar_split", "rows": rows, "emitted": emitted,
            "shared_sessions_march_2025": len(shared),
            "unmeasured": ["2026 lunar rows are PROJECTED throughout: no 2026 sighting has "
                           "happened, so a cell compiled on a 2026 feast date carries that label"],
            "targets": ("XNGUSD", "EURUSD", "XAUUSD")}


def mine_transmission_seeds(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The pack's own transmission map, emitted as HYPOTHESIS rows (every transfer domain)."""
    rows = [{"id": str(e["id"]), "target": str(e["target"]), "targets": tuple(e["targets"]),
             "evidence": str(e["evidence"]), "sign": str(e["sign"])}
            for e in TRANSMISSION_EDGES_SEED]
    emitted = sum(1 for r in rows
                  if _emit(ctx, "mgb_seed",
                           f"{r['id']} -> {', '.join(r['targets'])} [{r['evidence']}]"))
    return {"miner": "mgb_transmission_seeds", "rows": rows, "emitted": emitted,
            "unmeasured": [], "targets": tuple(sorted({t for e in TRANSMISSION_EDGES_SEED
                                                       for t in e["targets"]}))}


MINERS: dict[str, Any] = {
    "mine_pipeline_map": mine_pipeline_map,
    "mine_libya_outages": mine_libya_outages,
    "mine_currency_regimes": mine_currency_regimes,
    "mine_olive_campaign": mine_olive_campaign,
    "mine_minerals_flows": mine_minerals_flows,
    "mine_calendar_split": mine_calendar_split,
    "mine_transmission_seeds": mine_transmission_seeds,
}


def mine(ctx: Any = None) -> dict[str, Any]:
    """THE DEPARTMENT ENTRY. Pure python, no network, no LLM, no heavy import.

    It runs the pack's own miners over the pack's own data, emits through the department context
    when one is given, and returns a plain report when one is not. `cells_emitted` is the number
    that matters: it is how many testable cells this pack is offering the one gauntlet, and it is
    counted from `cells()` rather than claimed.
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
    return {"code": CODE, "jurisdictions": JURISDICTIONS,
            "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "emitted": emitted, "rows": rows, "unmeasured": unmeasured,
            "cells_emitted": len(minted),
            "cells_by_domain": {d["id"]: sum(1 for c in minted if c["domain"] == d["id"])
                                for d in DOMAINS},
            "datasets": len(DATASETS), "actors": len(ACTORS), "domains": len(DOMAINS),
            "edges": len(TRANSMISSION_EDGES_SEED), "interactions": len(INTERACTIONS),
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
        "language_notes": LANGUAGE_NOTES,
        "terminology": TERMINOLOGY, "source_classes": SOURCE_CLASSES,
        "source_layers": SOURCE_LAYERS, "layer_absences": LAYER_ABSENCES,
        "jurisdiction_absences": JURISDICTION_ABSENCES,
        "layer_terms": layer_terms(), "source_layer_coverage": source_layer_coverage(),
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
        "pipelines": PIPELINES, "libya_outages": LIBYA_OUTAGES,
        "libyan_terminals": LIBYAN_TERMINALS, "libyan_fields": LIBYAN_FIELDS,
        "ramadan_windows": RAMADAN_WINDOWS, "sighting_authorities": SIGHTING_AUTHORITIES,
        "weekend_by_jurisdiction": WEEKEND_BY_JURISDICTION,
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
    """The framework's HolidayRule shape: every closure the rule produces for 2024-2026, the
    fixed month-days it derives them from, and the UNION weekend -- because the four do not
    share one and a single field cannot hold a split."""
    dates = sorted({d.isoformat() for y in HOLIDAYS_RULE["years"] for d in market_holidays(y)})
    fixed = sorted({f"{m:02d}-{d:02d}"
                    for rows in FIXED_NATIONAL.values() for m, d, _n in rows})
    return {"dates": tuple(dates), "fixed_md": tuple(fixed),
            "weekly_closed": WEEKEND_WEEKDAYS,
            "notes": (f"{HOLIDAYS_RULE['authority']} || WEEKEND IS SPLIT: "
                      f"{WEEKEND_BY_JURISDICTION} -- the union is carried here because one field "
                      f"cannot hold four calendars; `weekend_weekdays(cc)` is the authority")}


def lab_kwargs() -> dict[str, Any]:
    """The keyword set `country_lab.CountryPack` is built from, in the shapes its coercion reads
    best: sources as rows AND as tagged lines, positioning and miners as strings, the holiday
    rule as dates, absent layers as a mapping."""
    data = as_dict()
    real = [s for s in SOURCE_CLASSES if not str(s["id"]).startswith("absent_")]
    data.update({
        "code": CODE,
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
