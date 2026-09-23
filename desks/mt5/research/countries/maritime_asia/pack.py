"""MARITIME AND HIMALAYAN ASIA: five single-factor economies whose one exposure is published.

THE THESIS, PLAINLY. Brunei, Timor-Leste, the Maldives, Bhutan and Afghanistan share NO
geography, no border, no currency bloc, no trade agreement and no religion in common across all
five. Putting them in one pack on a map would be indefensible. They are here for a MEASUREMENT
property instead, and it is the only claim this pack makes about them as a group:

    EACH IS A SMALL OR CLOSED ECONOMY WHOSE SINGLE DOMINANT EXPOSURE IS PUBLISHED AND UNHEDGED,
    WHICH MAKES EACH ONE A CLEAN SINGLE-FACTOR CASE.

That is rare and it is worth a department. Almost every economy a desk studies is a blend of a
dozen exposures nobody can decompose, so a finding is always contaminated by the factors the
study could not hold still. Here the decomposition is done BY THE ECONOMY ITSELF: Brunei is LNG,
Timor-Leste is one oil fund, the Maldives is tourist arrivals, Bhutan is monsoon hydro sold to
India, and Afghanistan is a border-trade and aid economy read through other countries' customs.
Five economies, five factors, each one published on a clock. The pack never claims the five move
together; MAR-L exists precisely to test whether the SINGLE-FACTOR PROPERTY ITSELF has any
cross-sectional content, and the honest prior is that it has very little.

WHAT IS EXACTLY EXECUTABLE, AND IT IS NOT A PROXY CLAIM.

  1. BRUNEI: THE PAR LINK MAKES USDSGD THE EXACT EXPRESSION OF BRUNEI'S EXTERNAL VALUE. The
     Brunei dollar and the Singapore dollar have been interchangeable AT PAR under the Currency
     Interchangeability Agreement since 12 June 1967 -- each is customary tender in the other
     country at 1:1, and the Brunei Darussalam Central Bank runs a currency board holding the
     backing. USDBND is not quoted by this broker and does not need to be: USDSGD IS USDBND, to
     the last decimal, by treaty. That is one of the cleanest executable transmissions available
     for any frontier economy on this desk's book and it is this pack's first edge.
  2. BHUTAN: THE NGULTRUM HAS BEEN PEGGED 1:1 TO THE INDIAN RUPEE SINCE 1974 and the rupee is
     legal tender in Bhutan in practice. USDINR, which the broker quotes, is therefore the EXACT
     expression of Bhutan's external value on the same footing as (1).
  3. TIMOR-LESTE IS THE DOLLAR. It adopted the US dollar outright in 2000 and never left it, so
     it has no exchange rate of its own and no monetary policy of its own: its policy rate is the
     FOMC's and its real exchange rate moves with the dollar against Indonesia, its dominant
     import source. There is nothing to proxy because there is nothing to price.
  4. MVR AND AFN ARE THE TWO GENUINE TRANSMISSION TARGETS. The rufiyaa is pegged inside a band
     (10.28-15.42 to the dollar since April 2011) and has sat on the weak edge ever since, with a
     public parallel premium; the afghani is managed by Da Afghanistan Bank's published auctions
     inside a cash economy. Both are in TRANSMISSION_TARGETS with their regimes, and neither is
     dressed up as tradable.

THE FOUR MECHANISMS, AND EACH ONE IS A GENUINE SINGLE-FACTOR ECONOMY.

  BRUNEI. Brunei LNG's Lumut plant started in 1972 and is one of the oldest in the world; its
  long-term contracts with Japanese and Korean buyers are published, as are the Energy
  Department's production and export series. The Hengyi refinery on Pulau Muara Besar, a Chinese
  joint venture, changed the country from a pure crude exporter into a refined-PRODUCT exporter
  on a dated timetable from 2019. The Brunei Investment Agency is opaque and publishes no
  holdings -- and THAT OPACITY IS A MEASUREMENT, recorded as a NO_LAWFUL_GROUND row with the
  lawful substitute (the IMF Article IV external-asset aggregate) named beside it, not a gap.

  TIMOR-LESTE. The Petroleum Fund publishes QUARTERLY AUDITED REPORTS with holdings and
  withdrawals. Bayu-Undan, which funded essentially the entire state budget, ceased production in
  2023 on a published, dated schedule. Greater Sunrise and the Tasi Mane south-coast pipeline
  decision are dated, published and repeatedly deferred. A sovereign wealth fund whose INFLOW HAS
  STOPPED while its statutory withdrawal rule continues is a dated, computable depletion path and
  it is all public: `fund_depletion_path` computes it here from the Fund's own published rule.

  THE MALDIVES. The Ministry of Tourism publishes ARRIVALS DAILY, BY NATIONALITY. Tourism is
  directly about a quarter of GDP and indirectly about seventy per cent of it. Against that sits
  a pegged rufiyaa whose reserves have repeatedly approached crisis levels and a dated external
  maturity wall whose repricing is public. Daily real-activity data against a pegged currency
  running low on reserves is a genuinely testable stress mechanism, and the 2020 tourism stop --
  an economy's single input going to approximately zero and back on dated borders -- is its
  natural experiment.

  BHUTAN. Generation follows the monsoon, so Bhutan EXPORTS power to India in summer and IMPORTS
  it in winter, every year, on a schedule the Druk Green Power Corporation publishes. It is also
  a large per-capita importer from India, and its rupee reserves have been constrained on dated
  occasions -- the 2012-13 rupee crunch is the worked case. `hydro_season` is the seasonal state
  a cell conditions on and it is computed, not typed.

  AFGHANISTAN IS THE LIMIT CASE AND IS HANDLED AS ONE. Since August 2021 the central bank's
  reserves have been frozen abroad, the banking system is largely disconnected from
  correspondents, and statistical publication has narrowed severely. What IS published and
  lawful: UN agency reporting (UNAMA, OCHA, WFP), the UN's own cash-shipment disclosures, the
  World Bank's Afghanistan Economic Monitor, Da Afghanistan Bank's published afghani auction
  results, and MIRROR CUSTOMS from Pakistan, Iran, China and Uzbekistan -- which is where the
  coal and mineral exports that grew sharply after 2021 are actually counted. Afghanistan holds
  very large but undeveloped lithium and copper resources (Mes Aynak's Chinese concession has a
  published history going back to 2008), and it was a major producer of the opium poppy, whose
  2022 ban produced a measured collapse of more than ninety-five per cent in cultivation in
  UNODC's published survey. THE OPIUM POINT IS RECORDED AS AN ECONOMIC OBSERVABLE WITH NO
  EXECUTABLE LEG (see `NO_EXECUTABLE_LEG`): it is a dated, quantified supply event in a commodity
  this desk will never trade, and its lawful, testable content is a RURAL INCOME shock whose only
  executable expression is the regional gold and trade channel. Saying that is worth more than
  inventing a symbol for it.

FOUR CALENDAR SYSTEMS ACROSS FIVE JURISDICTIONS, AND THAT IS THIS PACK'S DISTINGUISHING CALENDAR
FACT. Islamic lunar (Brunei, the Maldives, Afghanistan -- three different sighting authorities
that have produced different Eid dates in the same year), SOLAR HIJRI (Afghanistan, whose new
year and FISCAL year begin at the March equinox, which is DERIVED here and never typed), TIBETAN
LUNISOLAR (Bhutan -- Losar, Blessed Rainy Day and the Thimphu Tshechu, computed by the
Pangrizampa astrological institute and reproducible by no rule in this file, so they are typed
with that authority named), and GREGORIAN with the Catholic movable feasts (Timor-Leste, where
Easter is computed). A closure model that assumes one calendar mislabels four jurisdictions.

FIVE SCRIPTS AND AN ENGLISH-ONLY CRAWL READS NONE OF THEM: Malay in Jawi (Arabic script) and
Rumi, Tetum and PORTUGUESE (co-official in Timor-Leste and the language of its law -- a
genuinely distinctive Asian fact), Dhivehi in the right-to-left Thaana script, Dzongkha in
Tibetan script, and Dari and Pashto in Arabic script.

LAWFULNESS IS A FIRST-CLASS FIELD HERE, NOT A DISCLAIMER. See ACCESS_CONSTRAINTS: Afghanistan is
subject to extensive international measures and its de facto authorities are not recognised by
most states. Nothing in this pack touches any entity's private systems and nothing bypasses an
access control. Everything is PUBLIC -- national statistics and central-bank publications where
they exist, sovereign-fund audited reports, UN agency and World Bank publications, UNODC's
published surveys, and public press. Nothing here collects personal data about any individual.
Sanctions constrain TRANSACTIONS, not the reading of published statistics, and the desk executes
only broker symbols -- never an instrument of any of these five.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

# ruff: noqa: RUF001, RUF002, RUF003
# RUF001/2/3 flag characters that LOOK like Latin ones, to catch homoglyph attacks in
# IDENTIFIERS. This file deliberately carries Jawi, Thaana, Tibetan, Dari and Pashto text as
# DATA, because a miner that cannot match ދިވެހިރާއްޖެ or འབྲུག་ཡུལ། or د افغانستان بانک cannot find
# the release it is looking for. Suppressed file-wide and explained here rather than scattered as
# per-line noqa; NO identifier in this module is non-ASCII. Same decision `ru` and
# `caucasus_central_asia` took, for the same reason.

# --------------------------------------------------------------------------- identity
CODE = "MARITIME_ASIA"
NAME = "Maritime and Himalayan Asia (Brunei, Timor-Leste, Maldives, Bhutan, Afghanistan)"
REGION_COMMAND = "asia"
REGION_DESK = "MARITIME_HIMALAYAN_ASIA"
#: THE FOREST THE COORDINATOR SHOULD REGISTER THIS PACK ON. Three of the five (mv, bt, af) are
#: SAARC members and belong with `south_asia`; Brunei and Timor-Leste are ASEAN members and would
#: sit with `asean`. A pack registers on ONE forest, the South Asian half is the majority and the
#: two exact-expression legs (USDINR for Bhutan, the Indian tourist and credit channel for the
#: Maldives) point the same way -- so `south_asia` it is, and the ASEAN half is declared rather
#: than hidden (see BEYOND_ROSTER and INTERACTIONS['sg']).
FOREST = "south_asia"
CURRENCY = "BND"                   # the pack's lead currency; see CURRENCIES for all five
#: BRUNEI'S FISCAL YEAR, because BND is the lead. All five differ and all five are in
#: FISCAL_YEARS -- Afghanistan's does not even run on a Gregorian anchor.
FISCAL_YEAR_END = "03-31"
NATIVE_LANGUAGES: tuple[str, ...] = ("ms", "tet", "pt", "dv", "dz", "fa-AF", "ps", "en")
COT_CURRENCY = ""                  # no CFTC contract exists for BND, MVR, BTN or AFN
EXPORT_ECONOMY = "single_factor_exporters"
RETAIL_LEVERAGE_REGIME = "ABSENT"  # no licensed retail margin industry in any of the five

MISSION = ("mine five small or closed economies whose single dominant exposure is PUBLISHED and "
           "unhedged, as the clean single-factor cases they are: Brunei's LNG and its par link "
           "to the Singapore dollar, which makes USDSGD the EXACT expression of its external "
           "value; Timor-Leste's dollarised economy and the dated depletion path of the world's "
           "most fund-dependent state; the Maldives' DAILY tourist arrivals against a pegged "
           "rufiyaa with a published parallel premium and a dated maturity wall; Bhutan's "
           "monsoon hydro sold to India under a 1:1 rupee par that makes USDINR exact; and "
           "Afghanistan as the limit case, read through mirror customs, UN disclosures and "
           "published auctions with every absent layer named and substituted -- across four "
           "calendar systems and five scripts")

#: THE PARITY FENCE COUNTS THIS TUPLE (`scripts/check_regional_parity.py::jurisdictions_of`).
#: Five lowercase ISO-2 codes, and the pack owes EACH of them at least three actors, two domains
#: and source roots of its own. A multi-jurisdiction pack that credits itself with a country it
#: did not write is worse than a missing pack: the fence then reads the gap as closed.
JURISDICTIONS: tuple[str, ...] = ("bn", "tl", "mv", "bt", "af")

#: NONE OF THE FIVE IS ON ANY FOREST'S COUNTRY LIST AS OF 2026-09-23, and the pack says so rather
#: than implying a coverage the fence cannot cash. `libs/research/forests.py` is owned by the
#: coordinator and is NOT edited from here; adding these five to `south_asia` (or splitting bn
#: and tl onto `asean`) is the forest owner's call. The split is kept as two tables so that a
#: later registration only moves codes from one to the other and no test has to change.
ROSTER_JURISDICTIONS: tuple[str, ...] = ()
BEYOND_ROSTER: dict[str, str] = {
    "bn": "Brunei is on no forest's country list as of 2026-09-23. It is written here because "
          "the 1967 Currency Interchangeability Agreement makes USDSGD the EXACT expression of "
          "its external value -- the single cleanest executable transmission any frontier "
          "economy on this book offers -- and because its LNG export series is published",
    "tl": "Timor-Leste is on no forest's country list as of 2026-09-23. It is written here "
          "because it is the world's most sovereign-fund-dependent state, its fund publishes "
          "QUARTERLY AUDITED holdings and withdrawals, and its funding field ceased production "
          "in 2023 -- a dated, computable depletion path that exists nowhere else in public",
    "mv": "the Maldives is on no forest's country list as of 2026-09-23. It is written here "
          "because it publishes TOURIST ARRIVALS DAILY BY NATIONALITY, which is among the "
          "highest-frequency public real-activity series of any economy on earth, and it runs "
          "that series against a pegged currency with published reserves and a dated maturity",
    "bt": "Bhutan is on no forest's country list as of 2026-09-23. It is written here because "
          "the ngultrum's 1:1 rupee par makes USDINR the EXACT expression of its external value "
          "and because its hydro exports to India follow the MONSOON on a published seasonal "
          "cycle -- a physical, dated, annually repeating flow with an executable leg",
    "af": "Afghanistan is on no forest's country list as of 2026-09-23. It is written here as "
          "the pack's LIMIT CASE: the jurisdiction where most source layers are genuinely gone "
          "and the discipline of naming each absence with its lawful substitute -- mirror "
          "customs, UN disclosures, published auctions -- is worth more than any single series",
}

#: THE FIVE CURRENCIES AND THE REGIME EACH ONE ACTUALLY RUNS. Two of them are PAR-LINKED to a
#: currency the broker quotes, which is a different and much stronger claim than a proxy: a par
#: link is a treaty or a statute, not a correlation, so USDSGD and USDINR are EXACT EXPRESSIONS
#: and are labelled as such. One of them IS the dollar. Two of them are genuine transmission
#: targets with parallel premia. None of the five is a broker symbol.
CURRENCIES: dict[str, dict[str, Any]] = {
    "bn": {"iso": "BND", "name": "Brunei dollar (ringgit Brunei)",
           "regime": "CURRENCY BOARD at the Brunei Darussalam Central Bank, with full backing; "
                     "interchangeable AT PAR with the Singapore dollar under the Currency "
                     "Interchangeability Agreement of 12 June 1967, each being customary tender "
                     "in the other country at 1:1",
           "exact_expression": "USDSGD", "par_with": "SGD", "par_rate": 1.0,
           "broker_symbol": "", "since": "1967-06-12",
           "why": "NOT A PROXY. A treaty par at 1:1 means USDSGD and USDBND are the same number, "
                  "so every Brunei external-value cell is executable today with no basis risk "
                  "and no estimation step at all"},
    "tl": {"iso": "USD", "name": "the United States dollar (Timor-Leste is dollarised)",
           "regime": "FULL OFFICIAL DOLLARISATION since 2000; the US dollar is legal tender and "
                     "the only banknote in circulation, with locally minted centavo coins. "
                     "Banco Central de Timor-Leste is a currency board in all but name and has "
                     "no policy rate",
           "exact_expression": "US500", "par_with": "USD", "par_rate": 1.0,
           "broker_symbol": "", "since": "2000-01-24",
           "why": "THERE IS NOTHING TO PRICE. Timor-Leste's monetary policy is the FOMC's, so "
                  "its monetary cells are US-rate cells and its competitiveness cells run "
                  "against USDIDR, Indonesia being its dominant import source"},
    "mv": {"iso": "MVR", "name": "Maldivian rufiyaa",
           "regime": "pegged inside a BAND of plus or minus twenty per cent around 12.85 to the "
                     "US dollar since April 2011 (10.28 to 15.42); the rate has sat at or beside "
                     "the WEAK edge, 15.42, continuously since the band opened, with a published "
                     "and widely reported parallel-market premium above it",
           "exact_expression": "", "par_with": "", "par_rate": 0.0,
           "broker_symbol": "", "since": "2011-04-10",
           "why": "A TRANSMISSION TARGET, NOT A PRICE. A currency pinned on the weak edge of its "
                  "own band carries no information in its PRICE; the information is in the "
                  "DEFENCE -- the reserve path, the parallel premium and the maturity wall -- "
                  "and the executable legs are USDINR, XAUUSD and the US risk complex"},
    "bt": {"iso": "BTN", "name": "Bhutanese ngultrum",
           "regime": "pegged 1:1 to the INDIAN RUPEE since 1974 and maintained by the Royal "
                     "Monetary Authority; the Indian rupee circulates in Bhutan in practice, and "
                     "the binding constraint has never been the parity but the stock of RUPEE "
                     "reserves available to pay for imports",
           "exact_expression": "USDINR", "par_with": "INR", "par_rate": 1.0,
           "broker_symbol": "", "since": "1974-04-01",
           "why": "NOT A PROXY. A statutory 1:1 par makes USDINR and USDBTN the same number, so "
                  "Bhutan's external value is executable today; what is NOT executable is the "
                  "rupee-reserve constraint, which is the mechanism that actually binds"},
    "af": {"iso": "AFN", "name": "Afghan afghani",
           "regime": "managed by Da Afghanistan Bank through PUBLISHED FX AUCTIONS inside a "
                     "largely cash economy; central-bank reserves have been frozen abroad since "
                     "August 2021 and part were transferred to a Swiss-based fund in 2022, so "
                     "the authority manages a flow (auctions, and UN cash shipments) rather than "
                     "a stock. The money-changer market at Sarai Shahzada in Kabul is the public "
                     "price of record and its quotes are reported openly",
           "exact_expression": "", "par_with": "", "par_rate": 0.0,
           "broker_symbol": "", "since": "2021-08-15",
           "why": "A TRANSMISSION TARGET WITH A NAMED LAWFUL GROUND. The auction results and the "
                  "money-changer quotes are published; the desk reads them and executes nothing "
                  "in them. The executable legs are XAUUSD, USDINR and the industrial metals"},
}

#: Every instrument this pack may compile a cell against. All twenty-two are in the broker
#: registry and NONE is a single-name equity. The five local currencies are absent by
#: construction: two of them are par-linked to symbols that ARE here, one of them IS the dollar,
#: and two are transmission targets. Nothing in this tuple is an instrument OF these five
#: jurisdictions -- the desk executes only broker symbols, which is also the lawfulness answer.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "USDSGD", "SGDJPY", "AUDSGD", "EURSGD", "GBPSGD", "NZDSGD",   # Brunei, AT PAR, exactly
    "USDINR",                                                     # Bhutan, AT PAR, exactly
    "USDJPY", "USDCNH", "USDIDR", "USDTHB", "USDKRW",             # the buyers and the neighbours
    "XNGUSD", "XBRUSD", "XTIUSD",                                 # the LNG and oil factor
    "XAUUSD", "XCUUSD", "XALUSD",                                 # the store-of-value and mineral
    "US500", "NAS100", "JPN225", "HK50",                          # the risk and demand carriers
)

# --------------------------------------------------------------------------- what is NOT a symbol
#: THE FIVE LOCAL CURRENCIES AND THE VENUES, ROUTED. Two of the five rows are labelled
#: EXACT_EXPRESSION rather than `proxies`-with-basis-risk, because a treaty or statutory par at
#: 1:1 is not an approximation. The rest carry their regime and say where the information is.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "BND (the Brunei dollar) -- AT PAR WITH SGD, so USDSGD IS the expression",
     "venue": "the Brunei Darussalam Central Bank currency board and the Currency "
              "Interchangeability Agreement with the Monetary Authority of Singapore",
     "basis": "EXACT_EXPRESSION",
     "why": "THE PACK'S FIRST AND CLEANEST FACT. Since 12 June 1967 the Brunei dollar and the "
            "Singapore dollar have been interchangeable at 1:1, each customary tender in the "
            "other country, with BDCB holding the backing. USDBND is therefore USDSGD to the "
            "last decimal BY TREATY -- not a correlation, not a basket, not a proxy. Every "
            "Brunei external-value cell in this pack is executable today with zero basis risk, "
            "and that is why MAR-A is the pack's first domain rather than its LNG domain",
     "proxies": ("USDSGD", "SGDJPY", "EURSGD", "AUDSGD", "GBPSGD", "NZDSGD")},
    {"name": "BTN (the Bhutanese ngultrum) -- AT PAR WITH INR, so USDINR IS the expression",
     "venue": "the Royal Monetary Authority of Bhutan and the 1974 parity with the Indian rupee",
     "basis": "EXACT_EXPRESSION",
     "why": "the ngultrum has been held at 1:1 to the Indian rupee since 1974 and the rupee "
            "circulates in Bhutan in practice, so USDBTN is USDINR. The parity itself has never "
            "been the mechanism -- what binds is the STOCK of rupee reserves available to pay "
            "for Indian imports, which is published by the RMA and is not a price",
     "proxies": ("USDINR", "XAUUSD")},
    {"name": "USD in Timor-Leste -- the country IS dollarised, so there is no target at all",
     "venue": "Banco Central de Timor-Leste; the US dollar is legal tender outright",
     "basis": "IS_THE_NUMERAIRE",
     "why": "Timor-Leste adopted the US dollar in 2000 and has no currency of its own beyond "
            "centavo coins. It therefore has NO exchange rate to model and NO monetary policy to "
            "forecast: its policy rate is the FOMC's. The executable content is the dollar's own "
            "level against Indonesia (USDIDR), its dominant import source, and the US rate and "
            "risk complex the Fund itself is invested in",
     "proxies": ("USDIDR", "US500", "NAS100", "USDSGD")},
    {"name": "MVR (the Maldivian rufiyaa) -- a band pinned on its weak edge with a parallel "
             "premium above it",
     "venue": "the Maldives Monetary Authority; the interbank and the parallel market",
     "basis": "TRANSMISSION_TARGET",
     "why": "since April 2011 the rufiyaa has been pegged inside a band twenty per cent either "
            "side of 12.85 (10.28 to 15.42) and has sat AT OR BESIDE THE WEAK EDGE, 15.42, ever "
            "since. A currency pinned to one edge of its own band has no information in its "
            "price; the information is in the DEFENCE -- gross and usable reserves, the parallel "
            "premium, and the dated external maturities whose repricing is public. The 2026 "
            "sukuk maturity is the nearest dated stress point and it is in POLICY_ERAS",
     "proxies": ("USDINR", "XAUUSD", "US500", "USDJPY")},
    {"name": "AFN (the Afghan afghani) -- a managed auction currency in a cash economy",
     "venue": "Da Afghanistan Bank's published FX auctions; the Sarai Shahzada money-changer "
              "market in Kabul as the public price of record",
     "basis": "TRANSMISSION_TARGET",
     "why": "central-bank reserves have been frozen abroad since August 2021, so the authority "
            "manages a FLOW rather than a stock: the auction sizes and results are published, "
            "the UN's own US-dollar cash shipments are disclosed, and the money-changer quotes "
            "are reported openly. The desk reads all three and executes NONE of them; the "
            "lawful executable legs are gold, the Indian rupee and the industrial metals",
     "proxies": ("XAUUSD", "USDINR", "XCUUSD")},
    {"name": "The domestic securities venues: Bhutan's RSEB, the Maldives Stock Exchange, and "
             "NOTHING AT ALL in Brunei, Timor-Leste or Afghanistan",
     "venue": "Royal Securities Exchange of Bhutan; Maldives Stock Exchange",
     "basis": "NO_TRADABLE_VENUE",
     "why": "Bhutan's exchange lists a couple of dozen mostly state-linked issuers and trades in "
            "sessions rather than continuously; the Maldives Stock Exchange is smaller still. "
            "BRUNEI HAS NO STOCK EXCHANGE AT ALL, Timor-Leste has none, and Afghanistan has "
            "none. There is no domestic tape, no expiry clock, no short-interest series and no "
            "margin series anywhere in these five, so the equity leg of every mechanism here is "
            "another jurisdiction's index and the generic expiry miner correctly reports "
            "UNMEASURED",
     "proxies": ("US500", "NAS100", "JPN225", "HK50")},
    {"name": "Brunei LNG's long-term contract prices and the Lumut cargo programme",
     "venue": "Brunei LNG Sdn Bhd; the Japanese and Korean long-term offtakers",
     "basis": "NOT_A_BROKER_SYMBOL",
     "why": "the contracts are long-term, oil-indexed and not marked to a public screen, so the "
            "executable leg is the GAS AND OIL FACTOR itself (XNGUSD, XBRUSD, XTIUSD) with the "
            "buyer's index as the control. THE TRANSMISSION IS GENUINELY WEAK AND THE PACK SAYS "
            "SO: an oil-indexed long-term cargo repriced quarterly does not move with a Henry "
            "Hub screen intraday, and MAR-B's null is that XNGUSD carries nothing about Brunei",
     "proxies": ("XNGUSD", "XBRUSD", "XTIUSD", "JPN225", "USDKRW")},
)

#: OBSERVABLES WITH NO EXECUTABLE LEG OF THEIR OWN, ROUTED WITH THEIR CONTROL NAMED. Four of this
#: pack's five dominant factors are NOT broker symbols: an LNG contract, a tourist arrival, a
#: kilowatt-hour and a hectare of poppy. Each is routed here to the symbol that carries its
#: economics, WITH the control that separates the route from the world, and each row states how
#: strong the transmission actually is. A weak route declared weak is a measurement; a weak route
#: dressed as strong is how a desk gets a certificate it cannot cash.
NO_EXECUTABLE_LEG: tuple[dict[str, Any], ...] = (
    {"observable": "Brunei LNG long-term contract volumes and the Lumut loading programme",
     "jurisdiction": "bn", "route": ("XNGUSD", "XBRUSD", "JPN225", "USDKRW"),
     "strength": "WEAK",
     "control": "the Japanese and Korean LNG import price indices over the same quarters, and "
                "the global LNG freight and spot complex; a Brunei cargo effect must beat both",
     "why": "oil-indexed long-term contracts repriced on a quarterly formula do not move with a "
            "US gas screen. The honest prior is that XNGUSD carries NOTHING about Brunei at a "
            "daily horizon and this row exists so the pack measures that rather than assuming it"},
    {"observable": "Maldivian daily tourist arrivals by nationality",
     "jurisdiction": "mv", "route": ("USDINR", "XBRUSD", "US500"),
     "strength": "MODERATE",
     "control": "regional outbound travel from India, China and Europe over the same days, and "
                "the global risk complex; an arrivals effect that fires with world risk is "
                "world risk",
     "why": "the series is the highest-frequency real-activity print this pack has and it is "
            "genuinely informative about the SOURCE economies' discretionary demand -- but the "
            "Maldives itself has no executable instrument, so the route runs through the largest "
            "source market's currency and through the jet-fuel and oil leg of travel cost"},
    {"observable": "Bhutanese hydro generation and the summer-export / winter-import reversal",
     "jurisdiction": "bt", "route": ("USDINR", "XALUSD", "XCUUSD"),
     "strength": "WEAK",
     "control": "Indian national power demand and the all-India monsoon rainfall departure over "
                "the same months; Bhutan is a small share of the Indian grid and a monsoon that "
                "fills Bhutan's rivers fills India's too",
     "why": "the mechanism is real and annually repeating, but Bhutan is a small fraction of "
            "India's generation, so an effect on USDINR would be surprising. The route is "
            "declared WEAK and the row that matters is the reversal's effect on Bhutan's own "
            "rupee reserve, which has no executable leg either"},
    {"observable": "Afghan opium poppy cultivation and the April 2022 ban",
     "jurisdiction": "af", "route": ("XAUUSD", "USDINR"),
     "strength": "NONE_DIRECT",
     "control": "regional rural income proxies -- Pakistani and Iranian agricultural output and "
                "the region's gold demand over the same seasons -- and the 2023 wheat-price "
                "shock, which moved the same households for an unrelated reason",
     "why": "THE DESK WILL NEVER TRADE THIS COMMODITY AND NO BROKER SYMBOL EXPRESSES IT. It is "
            "recorded because it is a DATED, QUANTIFIED supply event -- UNODC measured a fall of "
            "more than ninety-five per cent in cultivation between the 2022 and 2023 surveys -- "
            "whose lawful, testable economic content is a RURAL INCOME shock across a large "
            "population. Its only executable expression is the regional store-of-value and trade "
            "channel, the effect is expected to be small and slow, and MAR-K says so up front"},
    {"observable": "The Timor-Leste Petroleum Fund's own portfolio (it is invested in US "
                   "equities and US Treasuries)",
     "jurisdiction": "tl", "route": ("US500", "NAS100"),
     "strength": "MECHANICAL",
     "control": "the Fund's published benchmark weights and the same quarters' index returns; a "
                "Fund result that is just the index is the index",
     "why": "THE ONE ROUTE HERE THAT IS ARITHMETIC RATHER THAN ECONOMIC. The Fund publishes its "
            "asset allocation, so its quarterly return is largely a known function of US index "
            "returns -- which means the executable direction runs BACKWARDS, from the index to "
            "the Fund's balance, and the interesting object is the WITHDRAWAL decision on top"},
)

# --------------------------------------------------------------------------- the central banks
#: The pack's lead authority. Brunei is the lead because BND is the lead currency and because a
#: currency board with a treaty par is the cleanest monetary object in the five.
CENTRAL_BANK: dict[str, Any] = {
    "name": "Brunei Darussalam Central Bank (BDCB) / Bank Pusat Brunei Darussalam",
    "short": "BDCB",
    "framework": "currency_board",
    "committee": "the BDCB Board; there is no monetary policy committee because a currency board "
                 "with a par link takes no rate decision of its own",
    "policy_instrument": "NONE OF ITS OWN. BDCB issues the Brunei dollar against full backing "
                         "and holds it interchangeable AT PAR with the Singapore dollar under "
                         "the 1967 Currency Interchangeability Agreement, so Brunei's monetary "
                         "conditions are the Monetary Authority of Singapore's, and MAS runs an "
                         "EXCHANGE-RATE policy (the S$NEER band) rather than a rate",
    "mandate": "monetary and financial stability, the currency board, banking and takaful "
               "supervision, and the payment systems",
    "decision_rule": "THERE IS NO DOMESTIC POLICY DECISION TO DATE. The transmitted clock is the "
                     "MAS Monetary Policy Statement, published twice a year in the base case "
                     "(April and October) and off-cycle when MAS moves between them; the `sg` "
                     "pack owns that clock and this pack reads it",
    "decision_calendar_rule": "DECLARED EMPTY ON PURPOSE. Copying the MAS calendar into a Brunei "
                              "pack would claim a domestic event where there is a transmitted "
                              "one; the generic central-bank miner reporting UNMEASURED here is "
                              "the correct answer (L1.28a)",
    "decision_dates": (),
    "dates_status": "EMPTY ON PURPOSE: Brunei has no domestic monetary decision to date. The "
                    "transmitted clock is MAS's and belongs to the `sg` pack",
    "decision_time_utc": "",
    "announce_local": "n/a -- BDCB publishes notices, not decisions",
    "dst_rule": "Asia/Brunei is UTC+8 all year with no daylight saving",
    "minutes_lag_days": 0,
    "publication_classes": ("laporan_tahunan", "statistik_kewangan", "kadar_pertukaran",
                            "notis_bdcb", "sukuk_al_ijarah_issuance"),
    "policy_rate_series": "BDCB:no_policy_rate_currency_board",
    "expected_rate_series": "UNMEASURED",
    "consensus_proxy": "the MAS S$NEER stance and Singapore's short rates; there is no Brunei "
                       "rate expectation to measure a surprise against and the pack says so "
                       "rather than inventing one",
    "consensus_proxy_trap": "a BDCB notice is NOT news. Treating one as an event is measuring "
                            "Singapore with a lag -- and, one link further up, the dollar",
    "reserves_clock": "BDCB publishes monetary and financial statistics and an annual report; "
                      "the SOVEREIGN external assets are held by the Brunei Investment Agency "
                      "and are NOT published at all, which is a NO_LAWFUL_GROUND row",
    "programme": "none; Brunei has no IMF programme and no public external debt of consequence",
    "off_cycle": (),
    "root": "https://www.bdcb.gov.bn",
}

#: ALL FIVE MONETARY AUTHORITIES, because a five-jurisdiction pack with one central bank would be
#: claiming four it had not read. Each row carries what the authority CAN do, which in four of
#: the five cases is much less than a central bank normally can.
CENTRAL_BANKS: dict[str, dict[str, Any]] = {
    "bn": {"name": "Brunei Darussalam Central Bank (BDCB)", "framework": "currency_board",
           "can_set_a_rate": False, "root": "https://www.bdcb.gov.bn",
           "anchor": "par with SGD under the 1967 Currency Interchangeability Agreement",
           "note": "formed in 2021 from the Autoriti Monetari Brunei Darussalam; it supervises "
                   "banks and takaful and issues sukuk al-ijarah, and it takes no rate decision"},
    "tl": {"name": "Banco Central de Timor-Leste (BCTL)", "framework": "dollarised",
           "can_set_a_rate": False, "root": "https://www.bancocentral.tl",
           "anchor": "the US dollar outright; there is no domestic currency to anchor",
           "note": "BCTL is ALSO the operational manager of the Petroleum Fund and the publisher "
                   "of its quarterly audited report, which is what makes it the most informative "
                   "central bank in this pack despite having no monetary policy at all"},
    "mv": {"name": "Maldives Monetary Authority (MMA)", "framework": "pegged_band",
           "can_set_a_rate": True, "root": "https://www.mma.gov.mv",
           "anchor": "a band of plus or minus twenty per cent around 12.85 to the dollar since "
                     "April 2011; the rate sits at the weak edge, 15.42",
           "note": "MMA publishes monthly statistics including gross reserves; the binding "
                   "question is USABLE reserves net of short-term obligations, which is the "
                   "number that has repeatedly approached crisis levels"},
    "bt": {"name": "Royal Monetary Authority of Bhutan (RMA)", "framework": "pegged_par",
           "can_set_a_rate": True, "root": "https://www.rma.org.bt",
           "anchor": "1:1 with the Indian rupee since 1974",
           "note": "the RMA sets a domestic rate that cannot diverge far from India's without "
                   "leaking through an open border; the constraint that actually binds is the "
                   "RUPEE reserve, which it publishes separately from convertible-currency "
                   "reserves -- an unusual and very useful split"},
    "af": {"name": "Da Afghanistan Bank (DAB)", "framework": "auction_managed",
           "can_set_a_rate": False, "root": "https://www.dab.gov.af",
           "anchor": "none; the afghani is managed through published FX auctions in a cash "
                     "economy, with reserves frozen abroad since August 2021",
           "note": "DAB publishes auction announcements and results and a reference rate. It "
                   "cannot conduct international settlement normally, its correspondent "
                   "relationships are largely severed, and the UN's disclosed US-dollar cash "
                   "shipments are a material part of the country's dollar supply"},
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Maldives Ministry of Tourism DAILY arrivals bulletin",
     "local": "published each day for the previous day, by nationality and by resort/guesthouse "
              "split, Indian/Maldives Time (UTC+5)",
     "time_utc": "06:00", "dst_rule": "none (Indian/Maldives Time is UTC+5 all year)",
     "instruments": ("USDINR", "XBRUSD", "US500"), "window_minutes": 120,
     "why": "THE HIGHEST-FREQUENCY PUBLIC REAL-ACTIVITY SERIES IN THIS PACK AND ONE OF THE "
            "HIGHEST ANYWHERE. A daily count of people who have physically arrived, split by the "
            "economy they came from, published with a one-day lag by a ministry with no "
            "incentive to smooth it"},
    {"name": "The BND/SGD par -- the Currency Interchangeability Agreement rate",
     "local": "continuous; 1 BND = 1 SGD by agreement, at every bank counter in both countries",
     "time_utc": "00:00", "dst_rule": "none (Asia/Brunei and Asia/Singapore are both UTC+8)",
     "instruments": ("USDSGD", "SGDJPY", "EURSGD"), "window_minutes": 1440,
     "why": "NOT A FIXING AT ALL, AND THAT IS THE POINT. There is no daily determination to "
            "read: the par is a treaty number that has not moved since 1967, so USDSGD's own "
            "tick IS Brunei's external value in real time"},
    {"name": "The BTN/INR par -- the Royal Monetary Authority's 1974 parity",
     "local": "continuous; 1 BTN = 1 INR, with the Indian rupee circulating alongside",
     "time_utc": "00:00", "dst_rule": "none (Asia/Thimphu is UTC+6)",
     "instruments": ("USDINR",), "window_minutes": 1440,
     "why": "the same shape as Brunei's: a statutory 1:1 par means USDINR IS Bhutan's external "
            "value, and the informative coordinate is not the price but the RUPEE RESERVE behind "
            "it, which the RMA publishes monthly and which is not a price at all"},
    {"name": "The RBI reference rate (the Indian leg Bhutan and the Maldives both sit on)",
     "local": "around 13:00 Asia/Kolkata on Indian business days",
     "time_utc": "07:30", "dst_rule": "none (Asia/Kolkata is UTC+5:30 all year)",
     "instruments": ("USDINR",), "window_minutes": 60,
     "why": "Bhutan's currency is this number by parity and the Maldives' largest tourist source "
            "market prices its holiday in it; the `ind` pack owns the fixing and this pack reads "
            "it rather than re-deriving a single one of India's mechanics"},
    {"name": "Da Afghanistan Bank FX auction announcement and result",
     "local": "auctions are announced and their results published by DAB, Asia/Kabul (UTC+4:30)",
     "time_utc": "05:30", "dst_rule": "none (Asia/Kabul is UTC+4:30 all year, a half-hour "
                                      "offset that a naive session model silently rounds away)",
     "instruments": ("XAUUSD", "USDINR"), "window_minutes": 120,
     "why": "the ONE regularly published monetary number Afghanistan still produces, and the "
            "only lawful window on the afghani's official price. It is read; it is never traded"},
    {"name": "The MAS Monetary Policy Statement (Brunei's transmitted policy clock)",
     "local": "around 08:00 Asia/Singapore on the statement day, twice a year in the base case",
     "time_utc": "00:00", "dst_rule": "none (Asia/Singapore is UTC+8)",
     "instruments": ("USDSGD", "SGDJPY", "AUDSGD", "EURSGD"), "window_minutes": 90,
     "why": "OWNED BY THE `sg` PACK. Named here because the par link means a MAS decision IS a "
            "Brunei monetary decision, transmitted with no lag and no discretion whatsoever -- "
            "the cleanest example in this package of a country whose policy is set abroad"},
    {"name": "LBMA gold price PM auction (the store-of-value leg for AFN and MVR)",
     "local": "15:00 Europe/London", "time_utc": "15:00", "dst_rule": "GMT/BST",
     "instruments": ("XAUUSD",), "window_minutes": 15,
     "why": "in a cash economy with a frozen central bank and in an atoll economy with a "
            "parallel dollar market, physical gold is the savings instrument of record and its "
            "dollar price is the one thing both populations can observe and the desk can trade"},
    {"name": "JKM and the Asian LNG spot assessment (the Brunei export factor's screen)",
     "local": "assessed daily by the price-reporting agencies for Northeast Asian delivery",
     "time_utc": "08:30", "dst_rule": "none",
     "instruments": ("XNGUSD", "JPN225", "USDKRW"), "window_minutes": 60,
     "why": "REGISTERED, NOT SCRAPED: the assessments are licensed. Brunei's own cargoes are "
            "sold on oil-indexed long-term contracts rather than at this screen, which is "
            "exactly why MAR-B's null is that the screen carries nothing about Brunei"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Timor-Leste Petroleum Fund QUARTERLY AUDITED REPORT", "kind": "quarter_end",
     "roll": "next", "window_utc": ("00:00", "12:00"),
     "instruments": ("US500", "NAS100", "XBRUSD"),
     "why": "THE PACK'S MOST INFORMATIVE SCHEDULED DISCLOSURE. Holdings, returns, receipts and "
            "WITHDRAWALS for a fund that is the whole state's balance sheet, audited, published "
            "by Banco Central de Timor-Leste on a quarterly clock"},
    {"name": "Maldives Ministry of Tourism daily arrivals", "kind": "day_of_month",
     "days": tuple(range(1, 32)), "roll": "next", "window_utc": ("06:00", "08:00"),
     "instruments": ("USDINR", "XBRUSD", "US500"),
     "why": "EVERY DAY, for the previous day. There is no month-end to wait for and no vintage "
            "problem worth the name, which is why this is the only genuinely daily conditioning "
            "series in this pack"},
    {"name": "MMA monthly monetary statistics and the reserve print", "kind": "month_end",
     "roll": "next", "window_utc": ("04:00", "10:00"),
     "instruments": ("USDINR", "XAUUSD", "US500"),
     "why": "the DEFENCE of the peg, published monthly; gross reserves are the headline and "
            "usable reserves net of short-term obligations are the number that binds"},
    {"name": "RMA monthly statistical bulletin and the RUPEE reserve split", "kind": "month_end",
     "roll": "next", "window_utc": ("03:00", "09:00"),
     "instruments": ("USDINR", "XAUUSD"),
     "why": "Bhutan reports rupee reserves SEPARATELY from convertible-currency reserves, which "
            "is unusual and is the whole point: the 2012-13 crunch was a rupee shortage inside "
            "an adequate overall reserve position"},
    {"name": "Bhutan hydro export settlement with the Indian buyers", "kind": "month_end",
     "roll": "previous", "window_utc": ("03:00", "09:00"),
     "instruments": ("USDINR", "XALUSD"),
     "why": "exports are invoiced in rupees under long-term agreements and settle monthly; the "
            "seasonal sign flips twice a year and the flip dates are the monsoon's, not a "
            "calendar quarter's"},
    {"name": "Brunei quarterly national accounts and the oil and gas production series",
     "kind": "quarter_end", "roll": "next", "window_utc": ("02:00", "08:00"),
     "instruments": ("XNGUSD", "XBRUSD", "USDSGD"),
     "why": "the Department of Economic Planning and Statistics publishes GDP with the oil and "
            "gas sector broken out, which in Brunei is most of the economy"},
    {"name": "Afghanistan fiscal year, beginning at NOWRUZ (1 Hamal)", "kind": "fiscal_year_end",
     "roll": "next", "window_utc": ("00:00", "23:59"),
     "instruments": ("XAUUSD", "USDINR"),
     "why": "the only fiscal year in this pack with no Gregorian anchor at all: it starts at the "
            "MARCH EQUINOX, which `nowruz()` derives. A model that assumes a 1 January or 1 "
            "April fiscal start mis-stamps every Afghan budget event by up to three months"},
    {"name": "Brunei fiscal year, 1 April to 31 March", "kind": "fiscal_year_end",
     "roll": "previous", "window_utc": ("00:00", "23:59"),
     "instruments": ("XNGUSD", "USDSGD"),
     "why": "the budget titah and the appropriation are dated to it; the Legislative Council "
            "sits in the weeks before"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "BRUNEI HAS NO STOCK EXCHANGE AT ALL", "index_symbols": (),
     "open_local": "n/a", "close_local": "n/a", "open_utc": "", "close_utc": "",
     "dst_rule": "none", "auction": "none",
     "expiry_rule": "NO LISTED SECURITIES MARKET AND NO DERIVATIVES. BDCB issues short-dated "
                    "sukuk al-ijarah to banks; there is no continuous market, no tape and no "
                    "expiry clock, so the generic expiry miner correctly reports UNMEASURED",
     "holidays": "the Brunei national calendar",
     "notes": "AN OECD-LEVEL GDP PER HEAD AND NO EQUITY MARKET. That is not a footnote: it means "
              "the entire domestic savings pool runs through banks, takaful, the Tabung Amanah "
              "Pekerja provident fund and the Brunei Investment Agency, NONE of which publishes "
              "holdings -- so this pack's only listed leg is another jurisdiction's index"},
    {"name": "Royal Securities Exchange of Bhutan (RSEB)", "index_symbols": (),
     "open_local": "09:00", "close_local": "13:00", "open_utc": "03:00", "close_utc": "07:00",
     "dst_rule": "none (Asia/Thimphu is UTC+6)",
     "auction": "session trading rather than continuous matching",
     "expiry_rule": "NO DERIVATIVES. A couple of dozen mostly state-linked issuers, thin "
                    "turnover, and capital controls on non-resident participation",
     "holidays": "the Bhutanese national calendar, which is lunisolar",
     "notes": "REGISTERED AND NEVER HUNTED. Every listed name here is a single name under the "
              "two-lane order (2026-09-06), the free float is tiny and the tape is too thin for "
              "any statistical claim; the exchange is named so the pack's absence of an equity "
              "leg is a measurement rather than an oversight"},
    {"name": "Maldives Stock Exchange (MSE) and the Capital Market Development Authority",
     "index_symbols": (), "open_local": "10:00", "close_local": "13:00",
     "open_utc": "05:00", "close_utc": "08:00", "dst_rule": "none (UTC+5)",
     "auction": "session trading; very few trading days have any turnover at all",
     "expiry_rule": "NO DERIVATIVES AND NO USABLE TAPE",
     "holidays": "the Maldivian national calendar, Islamic plus fixed Gregorian dates",
     "notes": "a handful of issuers, most of them state-linked; the sovereign's own sukuk trades "
              "OFFSHORE and that offshore price -- not this exchange -- is where the Maldives' "
              "credit risk is actually marked"},
    {"name": "TIMOR-LESTE AND AFGHANISTAN HAVE NO SECURITIES EXCHANGE",
     "index_symbols": (), "open_local": "n/a", "close_local": "n/a",
     "open_utc": "", "close_utc": "", "dst_rule": "none", "auction": "none",
     "expiry_rule": "NONE EXISTS IN EITHER JURISDICTION",
     "holidays": "n/a",
     "notes": "Timor-Leste's entire national savings are inside the Petroleum Fund, which is "
              "invested in US equities and US Treasuries -- so the country's equity exposure is "
              "US500 and NAS100 by construction, disclosed quarterly. Afghanistan has no "
              "securities market, and since 2021 has no normal correspondent banking either"},
    {"name": "The carriers: SGX-adjacent SGD crosses, the Indian rupee leg and the US indices",
     "index_symbols": ("US500", "NAS100", "JPN225", "HK50"),
     "open_local": "n/a (this row names the executable venues, not a domestic one)",
     "close_local": "n/a", "open_utc": "00:00", "close_utc": "21:00", "dst_rule": "US/EU DST",
     "auction": "the venues' own",
     "expiry_rule": "the carriers' own expiry clocks, owned by their own packs",
     "holidays": "the carriers' own calendars, which are NOT any of these five",
     "notes": "EVERY MECHANISM IN THIS PACK TERMINATES HERE. Five jurisdictions with no tradable "
              "domestic venue between them means the executable leg is always somebody else's "
              "market, which is why the calendar work matters: a Bhutanese or Maldivian closure "
              "does not close the instrument the cell trades"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "mar_maldives_arrivals", "start_utc": "06:00", "end_utc": "08:00",
     "notes": "the daily arrivals bulletin window, 11:00-13:00 Maldives time; the only genuinely "
              "daily scheduled information event in this pack"},
    {"name": "mar_singapore_open", "start_utc": "00:30", "end_utc": "03:00",
     "notes": "the Singapore morning, which is Brunei's morning at the same UTC+8 offset and is "
              "where the par-linked SGD crosses trade their first liquidity of the day"},
    {"name": "mar_india_session", "start_utc": "03:45", "end_utc": "10:00",
     "notes": "the Indian trading day, the executable window for Bhutan's par and for the "
              "Maldives' largest source market"},
    {"name": "mar_kabul_auction", "start_utc": "05:30", "end_utc": "07:30",
     "notes": "the DAB auction window, Asia/Kabul being UTC+4:30 -- a HALF-HOUR offset that a "
              "naive hour-bucketed session model rounds away and then mis-stamps"},
    {"name": "mar_dili_morning", "start_utc": "23:00", "end_utc": "02:00",
     "notes": "the Dili business morning, Asia/Dili being UTC+9 -- the earliest local clock in "
              "this pack and one hour ahead of Singapore despite sitting south of it"},
    {"name": "mar_us_session", "start_utc": "13:30", "end_utc": "20:00",
     "notes": "the New York session. It is here because Timor-Leste's entire national wealth is "
              "invested in it and because the dollar IS Timor-Leste's currency, so the US "
              "session is a domestic session for one of these five jurisdictions"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "Maldives daily tourist arrivals by nationality", "cadence": "daily",
     "time_utc": "06:00", "source": "Ministry of Tourism, Maldives",
     "actual_series": "MOT:daily_arrivals", "expected_series": "UNMEASURED",
     "notes": "by nationality and by accommodation type; there is no published consensus, so a "
              "surprise must be built against the pack's own seasonal-and-trend baseline and "
              "every such cell is a HYPOTHESIS until the baseline is itself validated"},
    {"name": "Timor-Leste Petroleum Fund quarterly audited report", "cadence": "quarterly",
     "time_utc": "UNMEASURED", "source": "Banco Central de Timor-Leste",
     "actual_series": "BCTL:petroleum_fund_quarterly", "expected_series": "n/a",
     "notes": "capital, returns, RECEIPTS and WITHDRAWALS, plus the asset allocation. The "
              "withdrawal line against the Estimated Sustainable Income rule is the single most "
              "informative number any of these five publishes"},
    {"name": "MMA monthly monetary and reserve statistics", "cadence": "monthly",
     "time_utc": "UNMEASURED", "source": "Maldives Monetary Authority",
     "actual_series": "MMA:gross_reserves", "expected_series": "UNMEASURED",
     "notes": "gross reserves, usable reserves, money supply and the rufiyaa rate; the gap "
              "between gross and usable is where the stress actually lives"},
    {"name": "RMA monthly statistical bulletin including RUPEE reserves", "cadence": "monthly",
     "time_utc": "UNMEASURED", "source": "Royal Monetary Authority of Bhutan",
     "actual_series": "RMA:rupee_reserves", "expected_series": "n/a",
     "notes": "the rupee/convertible split is the unusual and useful part; a rupee shortage "
              "inside an adequate total reserve is exactly what happened in 2012-13"},
    {"name": "Brunei quarterly GDP with the oil and gas sector broken out",
     "cadence": "quarterly", "time_utc": "UNMEASURED",
     "source": "Department of Economic Planning and Statistics (DEPS), Ministry of Finance and "
               "Economy", "actual_series": "DEPS:gdp_oil_gas", "expected_series": "UNMEASURED",
     "notes": "the non-oil economy is small enough that the headline is essentially a production "
              "and price series with a public sector attached"},
    {"name": "Brunei monthly crude, condensate and LNG production and export volumes",
     "cadence": "monthly", "time_utc": "UNMEASURED",
     "source": "Energy Department, Prime Minister's Office",
     "actual_series": "ENERGY:lng_exports", "expected_series": "n/a",
     "notes": "the pack's physical factor for Brunei; Hengyi's product exports appear here as a "
              "separate and NEWER line, which is the dated regime break of 2019"},
    {"name": "Da Afghanistan Bank FX auction announcements and results", "cadence": "weekly",
     "time_utc": "05:30", "source": "Da Afghanistan Bank",
     "actual_series": "DAB:fx_auction_result", "expected_series": "UNMEASURED",
     "notes": "size offered, size allotted and the cut-off; the one regularly published monetary "
              "number the jurisdiction still produces"},
    {"name": "World Bank Afghanistan Economic Monitor", "cadence": "semiannual",
     "time_utc": "UNMEASURED", "source": "World Bank",
     "actual_series": "WB:afghanistan_economic_monitor", "expected_series": "n/a",
     "notes": "THE SUBSTITUTE NATIONAL ACCOUNTS. Prices, trade, exchange rate, banking and "
              "fiscal, assembled from mirror and survey data with the method disclosed"},
    {"name": "UNODC Afghanistan opium survey", "cadence": "annual",
     "time_utc": "UNMEASURED", "source": "UN Office on Drugs and Crime",
     "actual_series": "UNODC:opium_cultivation_ha", "expected_series": "n/a",
     "notes": "satellite-and-ground cultivation area and farm-gate price. It is an ECONOMIC "
              "observable with NO executable leg (see NO_EXECUTABLE_LEG) and it is here because "
              "a fall of more than ninety-five per cent between two surveys is a dated, "
              "quantified income shock across a large rural population"},
    {"name": "Mirror customs: Pakistan, Iran, China and Uzbekistan monthly trade with "
             "Afghanistan", "cadence": "monthly", "time_utc": "UNMEASURED",
     "source": "Pakistan Bureau of Statistics / FBR, IRICA, China GACC, Uzbekistan Statistics "
               "Agency", "actual_series": "MIRROR:af_trade", "expected_series": "n/a",
     "notes": "THE LAWFUL SUBSTITUTE FOR AFGHAN TRADE STATISTICS, and the ground on which the "
              "post-2021 coal and mineral export growth is actually visible. A partner's "
              "customs table is a published statistic about the partner"},
    {"name": "Maldives Ministry of Finance debt bulletin and the external maturity profile",
     "cadence": "quarterly", "time_utc": "UNMEASURED", "source": "Ministry of Finance, Maldives",
     "actual_series": "MOF:external_debt_profile", "expected_series": "n/a",
     "notes": "the dated maturity wall, including the 2026 sukuk; the offshore price of that "
              "paper is the market's own reading and is not published by the ministry"},
    {"name": "Druk Green Power Corporation generation and export volumes", "cadence": "monthly",
     "time_utc": "UNMEASURED", "source": "Druk Green Power Corporation / Druk Holding and "
                                         "Investments", "actual_series": "DGPC:generation_gwh",
     "expected_series": "n/a",
     "notes": "the monsoon cycle in numbers; the winter IMPORT months are the same series with "
              "the sign flipped and are the part a summer-only study never sees"},
)

#: FIVE DIFFERENT FISCAL YEARS, AND ONE OF THEM HAS NO GREGORIAN ANCHOR. This is the kind of
#: thing a regional pack gets wrong by averaging: a budget event stamped to the wrong fiscal
#: boundary is a regime break placed in the wrong quarter.
FISCAL_YEARS: dict[str, dict[str, str]] = {
    "bn": {"end": "03-31", "start": "04-01",
           "note": "1 April to 31 March; the budget is delivered to the Legislative Council in "
                   "the weeks before it and is published in the gazette"},
    "tl": {"end": "12-31", "start": "01-01",
           "note": "the calendar year; the Orcamento Geral do Estado and the Petroleum Fund "
                   "transfer authorisation are voted inside it"},
    "mv": {"end": "12-31", "start": "01-01",
           "note": "the calendar year; the budget is submitted to the Majlis in the autumn"},
    "bt": {"end": "06-30", "start": "07-01",
           "note": "1 July to 30 June; the Five Year Plan cycle sits on top of it and is the "
                   "unit Bhutanese hydro investment is actually planned in"},
    "af": {"end": "DERIVED: the day before Nowruz", "start": "DERIVED: Nowruz (1 Hamal)",
           "note": "THE SOLAR HIJRI YEAR. The fiscal year begins at the MARCH EQUINOX under the "
                   "current de facto administration, having run from 1 Jadi (about 21 December) "
                   "between 1390 and 1400. `afghan_fiscal_year_start(year)` derives it from the "
                   "equinox rather than typing a date, because the equinox moves within the day "
                   "and across years and a typed date would be wrong within a decade"},
}

# ------------------------------------------------------- holidays: FOUR CALENDAR SYSTEMS
#: THE DISTINGUISHING CALENDAR FACT OF THIS PACK. Five jurisdictions run FOUR calendar systems
#: between them and no single rule computes more than one of them:
#:   (1) ISLAMIC LUNAR    -- Brunei, the Maldives, Afghanistan, under THREE DIFFERENT SIGHTING
#:                           AUTHORITIES that have produced different Eid dates in the same year;
#:   (2) SOLAR HIJRI      -- Afghanistan, whose new year AND fiscal year begin at the March
#:                           equinox, which is DERIVED here and never typed;
#:   (3) TIBETAN LUNISOLAR-- Bhutan, whose Losar, Blessed Rainy Day and Thimphu Tshechu are
#:                           computed by the Pangrizampa astrological institute and are
#:                           reproducible by NO rule in this file, so they are typed with that
#:                           authority named;
#:   (4) GREGORIAN with the CATHOLIC MOVABLE FEASTS -- Timor-Leste, where Easter IS computed.
#: A closure model that assumes one calendar mislabels four of the five jurisdictions.

#: The fixed civil dates, per jurisdiction, that recur on the same Gregorian day every year and
#: can therefore be computed rather than typed.
FIXED_NATIONAL: dict[str, tuple[tuple[int, int, str], ...]] = {
    "bn": ((1, 1, "Hari Tahun Baru Masihi (New Year's Day)"),
           (2, 23, "Hari Kebangsaan Negara Brunei Darussalam (National Day, 23 February)"),
           (5, 31, "Hari Angkatan Bersenjata Diraja Brunei (Royal Brunei Armed Forces Day)"),
           (7, 15, "Hari Keputeraan KDYMM (His Majesty the Sultan's Birthday)"),
           (12, 25, "Hari Natal (Christmas Day)")),
    "tl": ((1, 1, "Dia de Ano Novo / Loron Tinan Foun (New Year's Day)"),
           (5, 1, "Dia Mundial do Trabalhador / Loron Traballadores (Labour Day)"),
           (5, 20, "Dia da Restauracao da Independencia / Loron Restaurasaun Independensia "
                   "(Restoration of Independence, 20 May 2002)"),
           (8, 30, "Dia da Consulta Popular / Loron Konsulta Popular (Popular Consultation, "
                   "30 August 1999)"),
           (11, 1, "Dia de Todos os Santos (All Saints' Day)"),
           (11, 2, "Dia de Finados (All Souls' Day)"),
           (11, 12, "Dia Nacional da Juventude / Santa Cruz (National Youth Day)"),
           (11, 28, "Dia da Proclamacao da Independencia (Proclamation of Independence, "
                    "28 November 1975)"),
           (12, 7, "Dia da Memoria / Loron Eroi Nasional (National Heroes Day)"),
           (12, 8, "Dia de Nossa Senhora da Imaculada Conceicao, padroeira de Timor-Leste"),
           (12, 25, "Dia de Natal (Christmas Day)")),
    "mv": ((1, 1, "New Year's Day"),
           (5, 1, "Labour Day"),
           (7, 26, "Minivan Dhuvas (Independence Day, 26 July 1965)"),
           (7, 27, "Independence Day, second day"),
           (11, 3, "Nasrunlah Dhuvas (Victory Day)"),
           (11, 11, "Jumhooree Dhuvas (Republic Day)")),
    "bt": ((1, 1, "New Year's Day"),
           (1, 2, "Nyilo (Winter Solstice), a FIXED date in the Bhutanese civil list"),
           (2, 21, "Birth Anniversary of His Majesty the King, day 1 (21 February)"),
           (2, 22, "Birth Anniversary of His Majesty the King, day 2"),
           (2, 23, "Birth Anniversary of His Majesty the King, day 3"),
           (5, 2, "Birth Anniversary of the Third Druk Gyalpo"),
           (9, 23, "Thrue Bab / Blessed Rainy Day"),
           (11, 1, "Coronation of His Majesty the King"),
           (11, 11, "Birth Anniversary of the Fourth Druk Gyalpo, Constitution Day"),
           (12, 17, "Rgyal Yongs Dus Chen -- National Day (17 December 1907)")),
    "af": ((8, 15, "Victory of the Islamic Emirate (15 August), observed by the de facto "
                   "authorities since 2022"),
           (8, 19, "Independence Day (19 August 1919), observed historically and de-emphasised "
                   "by the de facto authorities")),
}

#: WHO DECIDES THE ISLAMIC DATES, NAMED PER JURISDICTION. Three sighting authorities, three
#: methods, and the dates DO diverge: in 2025 Afghanistan kept Eid al-Fitr on 30 March while
#: Brunei and the Maldives kept it on 31 March. That is not a data-quality problem to average
#: away -- it is the measurement, and a regional closure model that collapses it is wrong on one
#: of the three jurisdictions every time it happens.
SIGHTING_AUTHORITY: dict[str, str] = {
    "bn": "the Sultan of Brunei's decree on the advice of the Ministry of Religious Affairs; "
          "Brunei sights the moon LOCALLY and announces by titah, which is why its Eid has "
          "repeatedly fallen one day after Saudi Arabia's",
    "mv": "the Ministry of Islamic Affairs of the Maldives announces the dates; the Maldives has "
          "generally followed the regional sighting and its Eid has usually matched Brunei's",
    "af": "the de facto authorities' Supreme Court announces the sighting in Kabul; Afghanistan "
          "has repeatedly followed the Saudi determination and has therefore kept Eid one day "
          "BEFORE Brunei and the Maldives",
    "tl": "Timor-Leste declares Idul Fitri and Idul Adha national holidays by ANNUAL GOVERNMENT "
          "RESOLUTION and follows the Indonesian determination; a Catholic state keeping two "
          "Islamic holidays by resolution is one of the pack's better calendar facts",
    "bt": "NOT OBSERVED -- Bhutan keeps no Islamic date",
}

#: THE ISLAMIC DATES, TYPED BECAUSE NO RULE IN THIS FILE COMPUTES THEM. Rows are
#: (date, name, status, jurisdictions). A lunar date that depends on a local sighting cannot be
#: derived, so it is typed with its STATUS and its authority -- that is honest; a wrong rule with
#: a function wrapped round it is not. 2026 is PROJECTED throughout: no 1447/1448 sighting has
#: happened yet and every one of those dates can still move by a day.
ISLAMIC_FEASTS: dict[int, tuple[tuple[date, str, str, tuple[str, ...]], ...]] = {
    2024: ((date(2024, 2, 8), "Isra Mikraj (27 Rajab 1445)", "ANNOUNCED", ("bn",)),
           (date(2024, 3, 28), "Nuzul Al-Quran (17 Ramadan 1445)", "ANNOUNCED", ("bn",)),
           (date(2024, 4, 10), "Eid al-Fitr / Hari Raya Aidilfitri / Eid-ul Fithr, day 1",
            "ANNOUNCED", ("bn", "mv", "af", "tl")),
           (date(2024, 4, 11), "Eid al-Fitr, day 2", "ANNOUNCED", ("bn", "mv")),
           (date(2024, 6, 16), "Eid al-Adha / Eid-ul Al'haa (10 Dhu al-Hijjah 1445)",
            "ANNOUNCED", ("mv", "af", "tl")),
           (date(2024, 6, 17), "Hari Raya Aidiladha (Brunei kept the following day)",
            "ANNOUNCED", ("bn",)),
           (date(2024, 7, 7), "Awal Tahun Hijrah / Islamic New Year (1 Muharram 1446)",
            "ANNOUNCED", ("bn", "mv", "af")),
           (date(2024, 7, 16), "Ashura (10 Muharram 1446)", "ANNOUNCED", ("af", "mv")),
           (date(2024, 9, 16), "Mawlid / Maulidur Rasul (12 Rabi al-Awwal 1446)", "ANNOUNCED",
            ("bn", "mv", "af"))),
    2025: ((date(2025, 1, 27), "Isra Mikraj (27 Rajab 1446)", "ANNOUNCED", ("bn",)),
           (date(2025, 3, 17), "Nuzul Al-Quran (17 Ramadan 1446)", "ANNOUNCED", ("bn",)),
           (date(2025, 3, 30), "Eid al-Fitr -- AFGHANISTAN'S DAY, one ahead of Brunei's",
            "ANNOUNCED", ("af",)),
           (date(2025, 3, 31), "Eid al-Fitr / Hari Raya Aidilfitri, day 1", "ANNOUNCED",
            ("bn", "mv", "tl")),
           (date(2025, 4, 1), "Eid al-Fitr, day 2", "ANNOUNCED", ("bn", "mv")),
           (date(2025, 6, 6), "Eid al-Adha (10 Dhu al-Hijjah 1446)", "ANNOUNCED",
            ("mv", "af", "tl")),
           (date(2025, 6, 7), "Hari Raya Aidiladha (Brunei kept the following day)",
            "ANNOUNCED", ("bn",)),
           (date(2025, 6, 26), "Awal Tahun Hijrah / Islamic New Year (1 Muharram 1447)",
            "ANNOUNCED", ("bn", "mv", "af")),
           (date(2025, 7, 5), "Ashura (10 Muharram 1447)", "ANNOUNCED", ("af", "mv")),
           (date(2025, 9, 5), "Mawlid / Maulidur Rasul (12 Rabi al-Awwal 1447)", "ANNOUNCED",
            ("bn", "mv", "af"))),
    2026: ((date(2026, 1, 16), "Isra Mikraj (27 Rajab 1447)", "PROJECTED", ("bn",)),
           (date(2026, 3, 6), "Nuzul Al-Quran (17 Ramadan 1447)", "PROJECTED", ("bn",)),
           (date(2026, 3, 20), "Eid al-Fitr (1 Shawwal 1447) -- THE NOWRUZ COLLISION YEAR",
            "PROJECTED", ("bn", "mv", "af", "tl")),
           (date(2026, 3, 21), "Eid al-Fitr, day 2", "PROJECTED", ("bn", "mv")),
           (date(2026, 5, 27), "Eid al-Adha (10 Dhu al-Hijjah 1447)", "PROJECTED",
            ("bn", "mv", "af", "tl")),
           (date(2026, 6, 16), "Awal Tahun Hijrah / Islamic New Year (1 Muharram 1448)",
            "PROJECTED", ("bn", "mv", "af")),
           (date(2026, 6, 25), "Ashura (10 Muharram 1448)", "PROJECTED", ("af", "mv")),
           (date(2026, 8, 25), "Mawlid / Maulidur Rasul (12 Rabi al-Awwal 1448)", "PROJECTED",
            ("bn", "mv", "af"))),
}

#: BHUTAN'S TIBETAN LUNISOLAR DATES, TYPED WITH THE AUTHORITY THAT PRODUCES THEM. The Bhutanese
#: calendar is computed by the Pangrizampa astrological institute in Thimphu and published in the
#: Cabinet's annual list of public holidays. It is NOT the Tibetan calendar and it is NOT the
#: Chinese one: it can differ from both by a month in some years because of how the leap month is
#: inserted. NO RULE IN THIS FILE COMPUTES IT, so every row is typed and every row carries its
#: status -- which is honest. Rows are (date, name, status).
TIBETAN_LUNISOLAR: dict[int, tuple[tuple[date, str, str], ...]] = {
    2024: ((date(2024, 2, 11), "Losar -- Bhutanese New Year", "PROJECTED_PANGRIZAMPA"),
           (date(2024, 5, 23), "Lord Buddha's Parinirvana", "PROJECTED_PANGRIZAMPA"),
           (date(2024, 6, 16), "Birth Anniversary of Guru Rinpoche", "PROJECTED_PANGRIZAMPA"),
           (date(2024, 7, 9), "First Sermon of Lord Buddha", "PROJECTED_PANGRIZAMPA"),
           (date(2024, 9, 13), "Thimphu Tshechu, day 1", "PROJECTED_PANGRIZAMPA"),
           (date(2024, 9, 14), "Thimphu Tshechu, day 2", "PROJECTED_PANGRIZAMPA"),
           (date(2024, 9, 15), "Thimphu Tshechu, day 3", "PROJECTED_PANGRIZAMPA"),
           (date(2024, 11, 22), "Descending Day of Lord Buddha", "PROJECTED_PANGRIZAMPA")),
    2025: ((date(2025, 2, 28), "Losar -- Bhutanese New Year", "PROJECTED_PANGRIZAMPA"),
           (date(2025, 6, 10), "Lord Buddha's Parinirvana", "PROJECTED_PANGRIZAMPA"),
           (date(2025, 7, 5), "Birth Anniversary of Guru Rinpoche", "PROJECTED_PANGRIZAMPA"),
           (date(2025, 7, 28), "First Sermon of Lord Buddha", "PROJECTED_PANGRIZAMPA"),
           (date(2025, 10, 2), "Thimphu Tshechu, day 1", "PROJECTED_PANGRIZAMPA"),
           (date(2025, 10, 3), "Thimphu Tshechu, day 2", "PROJECTED_PANGRIZAMPA"),
           (date(2025, 10, 4), "Thimphu Tshechu, day 3", "PROJECTED_PANGRIZAMPA"),
           (date(2025, 11, 11), "Descending Day of Lord Buddha", "PROJECTED_PANGRIZAMPA")),
    2026: ((date(2026, 2, 18), "Losar -- Bhutanese New Year", "PROJECTED_PANGRIZAMPA"),
           (date(2026, 5, 31), "Lord Buddha's Parinirvana", "PROJECTED_PANGRIZAMPA"),
           (date(2026, 6, 24), "Birth Anniversary of Guru Rinpoche", "PROJECTED_PANGRIZAMPA"),
           (date(2026, 7, 17), "First Sermon of Lord Buddha", "PROJECTED_PANGRIZAMPA"),
           (date(2026, 9, 21), "Thimphu Tshechu, day 1", "PROJECTED_PANGRIZAMPA"),
           (date(2026, 9, 22), "Thimphu Tshechu, day 2", "PROJECTED_PANGRIZAMPA"),
           (date(2026, 9, 23), "Thimphu Tshechu, day 3", "PROJECTED_PANGRIZAMPA"),
           (date(2026, 11, 30), "Descending Day of Lord Buddha", "PROJECTED_PANGRIZAMPA")),
}

#: BRUNEI'S FIFTH CALENDAR ELEMENT, and it is here because leaving it out would be wrong rather
#: than tidy: Brunei gazettes CHINESE NEW YEAR as a public holiday for its Chinese community. It
#: is Chinese lunisolar, it is computed by nobody in this file, and it is typed.
CHINESE_NEW_YEAR: dict[int, date] = {
    2024: date(2024, 2, 10), 2025: date(2025, 1, 29), 2026: date(2026, 2, 17)}

#: The status labels a typed holiday row may carry. ANNOUNCED means the authority has published
#: it; PROJECTED means this pack computed or estimated it and the authority's own list has not
#: been read. A cell compiled on a PROJECTED row is a hypothesis, never a promotion.
HOLIDAY_STATUSES: tuple[str, ...] = (
    "ANNOUNCED", "PROJECTED", "PROJECTED_PANGRIZAMPA", "CONTESTED")

#: AFGHANISTAN'S CONTESTED DATES, DECLARED RATHER THAN TYPED INTO THE TABLE. Nowruz is the solar
#: new year and the fiscal-year start and is DERIVED from the equinox -- but its status as a
#: PUBLIC HOLIDAY has been contested under the de facto authorities since 2022, who have
#: discouraged its public observance while the solar calendar itself remains in administrative
#: use. Both facts are true at once and the pack carries both rather than picking one.
CONTESTED_OBSERVANCE: tuple[dict[str, str], ...] = (
    {"jurisdiction": "af", "day": "Nowruz (1 Hamal, the March equinox)",
     "status": "CONTESTED",
     "what_is_certain": "the SOLAR HIJRI calendar remains in administrative use and the FISCAL "
                        "YEAR begins at the equinox; that is derivable and is derived here",
     "what_is_contested": "whether the day is observed as a public holiday. The de facto "
                          "authorities have discouraged public Nowruz observance since 2022 "
                          "while the calendar and the fiscal anchor continue",
     "consequence": "the fiscal boundary is used as a dated event and the CLOSURE is carried as "
                    "UNMEASURED; a closure model that asserts either way is asserting"},
    {"jurisdiction": "af", "day": "19 August (Independence Day) and 28 April",
     "status": "CONTESTED",
     "what_is_certain": "both dates were national holidays before August 2021",
     "what_is_contested": "the de facto authorities have replaced the commemorative calendar "
                          "with 15 August and de-emphasised the older civic dates",
     "consequence": "carried in FIXED_NATIONAL with the change named, so a study spanning 2021 "
                    "knows it crossed a calendar regime break as well as a political one"},
)


def easter(year: int) -> date:
    """Gregorian Easter Sunday, by the anonymous Gregorian computus.

    THE CATHOLIC HALF OF TIMOR-LESTE'S CALENDAR IS DERIVABLE AND IS THEREFORE DERIVED. Good
    Friday, Holy Saturday and Easter Sunday are national holidays in a country whose law is
    written in Portuguese and whose patroness has a fixed December feast; typing them where a
    rule exists would be exactly the failure the depth rule names.
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
    """Timor-Leste's movable Catholic closures: Good Friday, Holy Saturday and Easter Sunday,
    plus Ash Wednesday, which the national holiday list also carries. Computed from `easter`."""
    sunday = easter(year)
    return {
        sunday - timedelta(days=46): "Quarta-feira de Cinzas (Ash Wednesday)",
        sunday - timedelta(days=2): "Sexta-feira Santa / Sesta-feira Santa (Good Friday)",
        sunday - timedelta(days=1): "Sabado Santo (Holy Saturday)",
        sunday: "Domingo de Pascoa / Loron Paskua (Easter Sunday)",
    }


def _julian_to_datetime(jd: float) -> datetime:
    """A Julian Day number to a UTC datetime, by Meeus chapter 7. Used only by the equinox."""
    jd = float(jd) + 0.5
    z = int(jd // 1)
    frac = jd - z
    if z >= 2299161:
        alpha = int((z - 1867216.25) / 36524.25)
        a = z + 1 + alpha - alpha // 4
    else:
        a = z
    b = a + 1524
    c = int((b - 122.1) / 365.25)
    d = int(365.25 * c)
    e = int((b - d) / 30.6001)
    day_with_frac = b - d - int(30.6001 * e) + frac
    day = int(day_with_frac)
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715
    seconds = int(round((day_with_frac - day) * 86400.0))
    return datetime(year, month, day, tzinfo=UTC) + timedelta(seconds=seconds)


#: Asia/Kabul is UTC+4:30 all year. A HALF-HOUR offset, which is why the Nowruz instant has to be
#: converted rather than eyeballed: an equinox at 19:40 UTC on the 20th is the 21st in Kabul.
KABUL_OFFSET = timedelta(hours=4, minutes=30)
#: How close to local midnight the derived equinox may fall before the pack refuses to name a
#: day. Meeus's MEAN-equinox expression is good to roughly a quarter of an hour over 1900-2100;
#: inside this margin the date is UNMEASURED rather than guessed (L1.28a).
EQUINOX_MIDNIGHT_MARGIN = timedelta(hours=1)


def march_equinox(year: int) -> datetime:
    """The March equinox instant in UTC, DERIVED, never typed.

    Meeus's expression for the mean March equinox (Astronomical Algorithms, chapter 27), which is
    accurate to roughly a quarter of an hour across 1900-2100 -- three orders of magnitude inside
    the one-day resolution a calendar needs. THE REASON THIS IS A FUNCTION AND NOT A TABLE is
    that Afghanistan's FISCAL YEAR starts here: the boundary moves within the day and across
    years, so a typed date is wrong within a decade and a study that stamps Afghan budget events
    to a fixed 21 March mis-dates them in roughly three years out of four.
    """
    y = (int(year) - 2000) / 1000.0
    jde0 = (2451623.80984 + 365242.37404 * y + 0.05169 * y**2
            - 0.00411 * y**3 - 0.00057 * y**4)
    return _julian_to_datetime(jde0)


def nowruz(year: int) -> date:
    """Nowruz in Afghanistan: the LOCAL day (Asia/Kabul, UTC+4:30) containing the equinox."""
    return (march_equinox(year) + KABUL_OFFSET).date()


def nowruz_is_certain(year: int) -> bool:
    """False when the derived instant sits within an hour of Kabul midnight, where the mean-
    equinox expression's residual error could move the DAY. A pack that cannot tell which day it
    is says so rather than picking one."""
    local = march_equinox(year) + KABUL_OFFSET
    since_midnight = timedelta(hours=local.hour, minutes=local.minute, seconds=local.second)
    return (EQUINOX_MIDNIGHT_MARGIN <= since_midnight
            <= timedelta(days=1) - EQUINOX_MIDNIGHT_MARGIN)


def afghan_fiscal_year_start(year: int) -> date:
    """The first day of the Afghan fiscal year falling in a Gregorian year: 1 Hamal, which IS
    Nowruz. The single most consequential derived date in this pack."""
    return nowruz(year)


def afghan_fiscal_year_end(year: int) -> date:
    """The last day of the Afghan fiscal year that STARTED in `year`: the day before the next
    Nowruz. It is never 31 December and never 31 March."""
    return nowruz(year + 1) - timedelta(days=1)


def national_holidays(jurisdiction: str, year: int) -> dict[date, str]:
    """One jurisdiction's closed days in one year, assembled from whichever calendars it runs.

    FOUR GENERATORS, APPLIED SELECTIVELY. Fixed civil dates for all five; the Catholic movable
    feasts for Timor-Leste only; the typed Islamic rows for the three that keep them (plus
    Timor-Leste's two resolution days); the typed Tibetan lunisolar rows for Bhutan only; the
    derived equinox for Afghanistan; and Brunei's gazetted Chinese New Year. NO WEEKEND
    SUBSTITUTION is applied anywhere: the substitution rules differ across the five, several are
    decreed per year rather than statutory, and inventing one would be worse than carrying the
    statutory day and saying so.
    """
    key = str(jurisdiction).lower()
    out: dict[date, str] = {}
    for month, day, name in FIXED_NATIONAL.get(key, ()):
        out[date(year, month, day)] = name
    if key == "tl":
        for day_, name in catholic_movable(year).items():
            out[day_] = name
    if key == "bt":
        for day_, name, status in TIBETAN_LUNISOLAR.get(year, ()):
            out[day_] = f"{name} [{status}]"
    if key == "bn" and year in CHINESE_NEW_YEAR:
        out[CHINESE_NEW_YEAR[year]] = "Tahun Baru Cina (Chinese New Year) [ANNOUNCED]"
    for day_, name, status, where in ISLAMIC_FEASTS.get(year, ()):
        if key in where:
            out[day_] = f"{name} [{status}]"
    if key == "af":
        day_ = nowruz(year)
        status = "CONTESTED" if nowruz_is_certain(year) else "CONTESTED_DAY_UNMEASURED"
        out[day_] = (f"Nowruz / 1 Hamal -- the SOLAR HIJRI new year and the FISCAL YEAR START, "
                     f"derived from the March equinox [{status}]")
    return dict(sorted(out.items()))


def regional_holidays(year: int) -> dict[date, tuple[str, ...]]:
    """Every closed day anywhere in the five, with WHICH jurisdictions close on it. A day that
    shuts one of five is a completely different liquidity object from a day that shuts three,
    and this pack's whole point is that the five do not move together."""
    out: dict[date, list[str]] = {}
    for key in JURISDICTIONS:
        for day in national_holidays(key, year):
            out.setdefault(day, []).append(key)
    return {d: tuple(sorted(v)) for d, v in sorted(out.items())}


def market_holidays(year: int) -> dict[date, str]:
    """The regional closure table for one year, WEEKDAYS ONLY -- a Saturday closure costs no
    session and must never enter a holiday-liquidity sample as though it did."""
    out: dict[date, str] = {}
    for day, where in regional_holidays(year).items():
        if day.weekday() >= 5:
            continue
        names = {national_holidays(k, year)[day] for k in where}
        out[day] = f"{'/'.join(where)}: {sorted(names)[0]}"
    return out


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


def closure_breadth(day: date) -> int:
    """How many of the five are shut on a date. THE STATE VARIABLE OF MAR-M: one of five is
    noise, four of five is a genuinely different regional day."""
    return len(regional_holidays(day.year).get(day, ()))


def calendar_systems(jurisdiction: str) -> tuple[str, ...]:
    """Which calendar systems one jurisdiction actually runs. THE PACK'S DISTINGUISHING FACT,
    computed rather than asserted: five jurisdictions, four systems, and two of the five run
    more than one system at once."""
    key = str(jurisdiction).lower()
    systems: list[str] = ["gregorian_civil"]
    if key in ("bn", "mv", "af", "tl"):
        systems.append("islamic_lunar")
    if key == "af":
        systems.append("solar_hijri")
    if key == "bt":
        systems.append("tibetan_lunisolar")
    if key == "tl":
        systems.append("gregorian_catholic_movable")
    if key == "bn":
        systems.append("chinese_lunisolar")
    return tuple(systems)


def eid_nowruz_collision(year: int) -> int | None:
    """Days between Eid al-Fitr and Nowruz in Afghanistan, or None when the year is not declared.

    THE 2026 CASE IS WHY THIS FUNCTION EXISTS. Eid al-Fitr drifts about eleven days earlier each
    solar year, so it walks into the March equinox roughly once a generation. In 2026 the
    projected Eid and the derived Nowruz land on the SAME DAY in Kabul -- which merges the
    Islamic and the Solar Hijri new-year closures into one block, in the one jurisdiction that
    runs both calendars, in the week its FISCAL YEAR turns over. A study that treats them as
    independent events double-counts that year; a study that conditions on 'a Nowruz week' pools
    a one-day boundary with a multi-day one.
    """
    for day, name, _status, where in ISLAMIC_FEASTS.get(year, ()):
        if "Eid al-Fitr" in name and "af" in where:
            return (day - nowruz(year)).days
    return None


def collision_years(window: int = 3) -> tuple[int, ...]:
    """The declared years in which Eid al-Fitr falls within `window` days of Nowruz."""
    out: list[int] = []
    for year in sorted(ISLAMIC_FEASTS):
        gap = eid_nowruz_collision(year)
        if gap is not None and abs(gap) <= window:
            out.append(year)
    return tuple(out)


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "four_calendar_systems_computed_and_typed_per_jurisdiction",
    "authority": "five national authorities and four calendar systems. Brunei: the Sultan's "
                 "titah on the advice of the Ministry of Religious Affairs, with a LOCAL moon "
                 "sighting. The Maldives: the Ministry of Islamic Affairs. Afghanistan: the de "
                 "facto authorities' Supreme Court, which has repeatedly followed the Saudi "
                 "determination. Bhutan: the Cabinet's annual list, whose lunisolar dates are "
                 "computed by the PANGRIZAMPA astrological institute in Thimphu. Timor-Leste: "
                 "the Government's annual resolution, published in the Jornal da Republica, "
                 "which fixes the Catholic dates AND declares Idul Fitri and Idul Adha",
    "rule": "FIVE JURISDICTIONS RUNNING FOUR DIFFERENT CALENDAR SYSTEMS IS THIS PACK'S "
            "DISTINGUISHING CALENDAR FACT, and no single rule computes more than one of them. "
            "(1) ISLAMIC LUNAR, kept by Brunei, the Maldives and Afghanistan under THREE "
            "DIFFERENT SIGHTING AUTHORITIES that have produced DIFFERENT DATES IN THE SAME YEAR "
            "-- in 2025 Afghanistan kept Eid al-Fitr on 30 March while Brunei and the Maldives "
            "kept it on 31 March, and Brunei has repeatedly kept Eid al-Adha one day after the "
            "other two. Typed in ISLAMIC_FEASTS with a status and the authority named, because "
            "a sighting cannot be derived. Brunei additionally keeps Isra Mikraj and Nuzul "
            "Al-Quran, which the other two do not. (2) SOLAR HIJRI, run by Afghanistan, whose "
            "new year is NOWRUZ at the March equinox and whose FISCAL YEAR BEGINS THERE -- "
            "DERIVED by `march_equinox`/`nowruz` and never typed, because the boundary moves "
            "within the day and across years. Its status as a public HOLIDAY is CONTESTED under "
            "the de facto authorities and is carried as such rather than asserted either way. "
            "(3) TIBETAN LUNISOLAR, run by Bhutan -- Losar, the Blessed Rainy Day, the Thimphu "
            "Tshechu and the Buddhist anniversaries -- computed by the Pangrizampa astrological "
            "institute and reproducible by NO rule in this file, so TYPED with that authority "
            "named. Bhutan also keeps FIXED civil dates: 17 DECEMBER NATIONAL DAY and the "
            "King's birthday on 21 FEBRUARY, both computed. (4) GREGORIAN WITH THE CATHOLIC "
            "MOVABLE FEASTS, run by Timor-Leste, where Ash Wednesday, Good Friday, Holy "
            "Saturday and Easter ARE computed from `easter(year)` -- derivable, therefore "
            "derived -- alongside 20 MAY (Restoration), 30 AUGUST (Popular Consultation) and "
            "28 NOVEMBER (Proclamation of Independence). Brunei adds a fifth element with its "
            "gazetted CHINESE NEW YEAR. The Maldives adds 26 JULY Independence. NO WEEKEND "
            "SUBSTITUTION is applied anywhere: the five rules differ, several are decreed per "
            "year rather than statutory, and inventing one would be worse than carrying the "
            "statutory day. THE CLOCKS ALSO DIFFER: Asia/Dili is UTC+9, Asia/Brunei UTC+8, "
            "Asia/Thimphu UTC+6, Indian/Maldives UTC+5 and Asia/Kabul UTC+4:30 -- a half-hour "
            "offset an hour-bucketed session model silently rounds away.",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday in Timor-Leste, the Maldives and Bhutan; Friday and Sunday "
               "in BRUNEI, whose weekly closure is Friday and Sunday with Saturday a working "
               "day -- a pattern shared with almost nothing else on this desk's book; Friday in "
               "Afghanistan, with Thursday a short day",
    "national_rule": "see `rule`; `national_holidays(jurisdiction, year)` is the computed form",
    "market_rule": "the union across the five, weekdays only; `closure_breadth(day)` says how "
                   "many of the five are actually shut, which is the state a liquidity study "
                   "conditions on rather than a binary flag. NONE OF THE FIVE HAS A TRADABLE "
                   "DOMESTIC VENUE, so a closure here never closes the instrument a cell trades "
                   "-- it removes the jurisdiction's own reporting and physical activity, which "
                   "is a different and much weaker object and the pack says so",
    "moon_sighting_rule": "LOCAL AND DIVERGENT. Brunei sights locally and announces by titah; "
                          "the Maldives announces through its Ministry of Islamic Affairs; "
                          "Afghanistan has repeatedly followed the Saudi determination. The "
                          "divergence is the measurement, not noise to average away",
    "moving_feasts": "the Islamic dates drift about eleven days earlier each solar year; in 2026 "
                     "the projected Eid al-Fitr and the DERIVED Nowruz fall on the same day in "
                     "Kabul, merging two new-year closures in the one jurisdiction that runs "
                     "both calendars -- see `eid_nowruz_collision`",
    "derived_vs_typed": "DERIVED: the Catholic movable feasts (from Easter) and Nowruz (from the "
                        "March equinox). TYPED WITH AN AUTHORITY: every Islamic date, every "
                        "Bhutanese lunisolar date and Brunei's Chinese New Year. The split is "
                        "the rule -- derive what a rule produces, type what a sighting or an "
                        "astrological institute produces, and never invent a rule for either",
    "bhutan_authority": "the Pangrizampa astrological institute in Thimphu computes the "
                        "Bhutanese calendar and the Cabinet publishes the annual holiday list",
    "afghanistan_status": "the SOLAR HIJRI calendar and the equinox fiscal boundary are certain "
                          "and derived; the OBSERVANCE of Nowruz as a public holiday is "
                          "CONTESTED under the de facto authorities and is carried as such",
    "table": {y: {d.isoformat(): (f"{'/'.join(w)}: "
                                  f"{sorted({national_holidays(k, y)[d] for k in w})[0]}")
                  for d, w in regional_holidays(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {2024: "ANNOUNCED for the Islamic and fixed rows; PROJECTED_PANGRIZAMPA for every "
                     "Bhutanese lunisolar row",
               2025: "ANNOUNCED for the Islamic and fixed rows; PROJECTED_PANGRIZAMPA for every "
                     "Bhutanese lunisolar row",
               2026: "PROJECTED throughout the Islamic rows -- no 1447/1448 sighting has "
                     "happened and every date can still move by a day; PROJECTED_PANGRIZAMPA "
                     "for Bhutan; the Timor-Leste and fixed civil rows are computed and firm"},
    "known_dates": {
        "2024-04-10": "Eid al-Fitr on one day across Brunei, the Maldives, Afghanistan and "
                      "Timor-Leste -- the years the three sighting authorities agree",
        "2025-03-30": "Eid al-Fitr in AFGHANISTAN, one day before Brunei's and the Maldives' -- "
                      "the divergence, typed rather than averaged",
        "2025-04-18": "Good Friday in Timor-Leste, COMPUTED from Easter 2025-04-20",
        "2026-03-20": "the COLLISION: the projected Eid al-Fitr and the DERIVED Nowruz on the "
                      "same Kabul day, in the week the Afghan fiscal year turns over",
        "2026-12-17": "Bhutan's National Day, a fixed solar date certain in every year",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "breadth_fn": closure_breadth,
    "equinox_fn": nowruz,
    "systems_fn": calendar_systems,
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "Timor-Leste Petroleum Fund quarterly holdings and withdrawals (audited)",
     "root": "https://www.bancocentral.tl/en/go/petroleum-fund-quarterly-reports",
     "fields": ("fund_capital", "quarterly_return", "petroleum_receipts", "transfers_to_state",
                "estimated_sustainable_income", "asset_allocation_equity_bond"),
     "frequency": "quarterly", "snapshot": "quarter end", "publish_utc": "UNMEASURED",
     "lag_days": 45, "licence": "free, public", "available": True,
     "why": "THE BEST POSITIONING SERIES IN THIS PACK AND ONE OF THE BEST PUBLIC SOVEREIGN-FUND "
            "DISCLOSURES ANYWHERE. A state whose entire balance sheet is one audited fund, "
            "publishing its capital, its allocation, its receipts AND its withdrawals every "
            "quarter. The withdrawal line against the statutory Estimated Sustainable Income is "
            "where the depletion path is actually visible",
     "pit_warning": "about six weeks late and quarter-end stamped; it conditions a quarter and "
                    "never a week, and the audited version can restate the unaudited one"},
    {"name": "Maldives Monetary Authority gross and usable reserves",
     "root": "https://www.mma.gov.mv/#/statistics",
     "fields": ("gross_reserves", "usable_reserves", "reserve_months_of_imports",
                "currency_in_circulation", "rufiyaa_rate"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "UNMEASURED",
     "lag_days": 30, "licence": "free, public", "available": True,
     "why": "THE DEFENCE OF THE PEG, and the gap between GROSS and USABLE is the whole "
            "measurement: a headline reserve number that includes short-term obligations has "
            "repeatedly been several times the number actually available",
     "pit_warning": "revised, and the usable definition has changed; a series spliced across "
                    "definition changes is measuring the definition"},
    {"name": "Royal Monetary Authority of Bhutan RUPEE reserves, reported separately",
     "root": "https://www.rma.org.bt/publication.jsp",
     "fields": ("rupee_reserves", "convertible_currency_reserves", "total_reserves",
                "months_of_essential_imports"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "UNMEASURED",
     "lag_days": 45, "licence": "free, public", "available": True,
     "why": "AN UNUSUAL AND VERY USEFUL SPLIT. Bhutan reports rupee reserves apart from "
            "convertible ones because the binding constraint is rupees for Indian imports, not "
            "hard currency in aggregate -- which is exactly what the 2012-13 crunch was",
     "pit_warning": "the bulletin is slow and the split's definition has moved; a level read off "
                    "a recent bulletin is not the level that was known at the time"},
    {"name": "Maldives external debt and maturity profile (Ministry of Finance)",
     "root": "https://www.finance.gov.mv/publications",
     "fields": ("external_debt_stock", "maturity_profile", "guaranteed_debt", "sukuk_2026"),
     "frequency": "quarterly", "snapshot": "quarter end", "publish_utc": "UNMEASURED",
     "lag_days": 60, "licence": "free, public", "available": True,
     "why": "the dated wall. A maturity schedule is the one forward-looking public number a "
            "small open economy cannot revise away, and the offshore price of the sovereign's "
            "own paper is the market's reading of it",
     "pit_warning": "the bulletin lags a quarter; the market's repricing happens long before it"},
    {"name": "a CFTC, exchange or dealer positioning series for BND, MVR, BTN or AFN",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: no future, forward or option on any of the four trades on any "
            "exchange the desk can read, and no COT contract exists for any of them anywhere",
     "pit_warning": "DOES NOT EXIST. BND positioning is never proxied by SGD positioning -- SGD "
                    "positioning is a position in the currency Brunei is pegged TO, and the same "
                    "applies to INR for the ngultrum. The par makes the PRICE identical and it "
                    "does NOT make the positioning identical, and conflating the two would be "
                    "the exact error this pack's par-link claim invites"},
    {"name": "a domestic equity, margin or short-interest series in any of the five",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: Brunei, Timor-Leste and Afghanistan have NO securities exchange at "
            "all; Bhutan's RSEB and the Maldives Stock Exchange are session-traded venues with a "
            "couple of dozen mostly state-linked issuers between them and no usable tape",
     "pit_warning": "DOES NOT EXIST. There is no order book, no short interest, no retail margin "
                    "and no derivatives clock anywhere in these five, so the generic expiry and "
                    "positioning miners correctly report UNMEASURED rather than borrowing a "
                    "neighbour's"},
    {"name": "Da Afghanistan Bank FX auction sizes and allotments",
     "root": "https://www.dab.gov.af",
     "fields": ("auction_offered_usd", "auction_allotted_usd", "cut_off_rate",
                "reference_rate_afn"),
     "frequency": "weekly", "snapshot": "auction day", "publish_utc": "05:30",
     "lag_days": 0, "licence": "free, public", "available": True,
     "why": "the only regular monetary flow Afghanistan still publishes, and the closest thing "
            "the jurisdiction has to a positioning series: the size the authority is willing to "
            "sell is the size it thinks it must",
     "pit_warning": "publication has been intermittent and the site's availability from outside "
                    "the country is not guaranteed; an unread auction is UNMEASURED, never zero"},
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

# ------------------------------------------------------------------ FIVE SCRIPTS, DETECTED
#: Arabic script, used here by BOTH Jawi (Malay) and Dari/Pashto -- two completely different
#: languages sharing one script, which is why the marker tables below exist beside the detector.
_ARABIC_RANGES = ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF),
                  (0xFB50, 0xFDFF), (0xFE70, 0xFEFF))
#: Thaana, the Maldivian script. RIGHT-TO-LEFT, derived from Arabic numerals rather than Arabic
#: letters, and used by no other language on earth.
_THAANA_RANGES = ((0x0780, 0x07BF),)
#: Tibetan script, used here for Dzongkha.
_TIBETAN_RANGES = ((0x0F00, 0x0FFF),)
_SCRIPTS: dict[str, tuple[tuple[int, int], ...]] = {
    "arabic": _ARABIC_RANGES, "thaana": _THAANA_RANGES, "tibetan": _TIBETAN_RANGES}

#: JAWI is Malay written in an extended Arabic script and it is CO-OFFICIAL in Brunei: the
#: gazette masthead, the titah, the religious-affairs notices and the Malay-language press all
#: carry it. A crawler that reads only Rumi (Latin Malay) misses the religious and ceremonial
#: register entirely -- which in Brunei is where the holiday decisions and the succession-adjacent
#: announcements actually live.
JAWI_MARKERS: tuple[str, ...] = (
    "بروني دارالسلام", "كراجاءن", "ميڽق دان ݢس", "تيتح", "وارتا كراجاءن",
    "هاري راي عيدالفطري", "هاري راي عيدالاضحى", "مولود الرسول", "اسرا معراج",
    "نزول القرءان", "دولار بروني", "بنك ڤوسة")
#: Malay in Rumi (the Latin orthography), which is the working script of the statistics office.
MALAY_MARKERS: tuple[str, ...] = (
    "minyak dan gas", "gas asli cecair", "Kementerian Kewangan dan Ekonomi",
    "Jabatan Perancangan Ekonomi dan Statistik", "Perjanjian Pertukaran Mata Wang",
    "dolar Brunei", "eksport", "pengeluaran minyak mentah", "Hari Kebangsaan", "titah",
    "warta kerajaan", "kilang penapisan", "Pulau Muara Besar", "Agensi Pelaburan Brunei",
    "Tabung Amanah Pekerja", "Hari Raya Aidilfitri", "Autoriti Monetari")
#: Tetum, Timor-Leste's other official language and the one the street speaks.
TETUM_MARKERS: tuple[str, ...] = (
    "Fundu Petroliferu", "Banku Sentral", "osan", "folin", "loron", "Konsulta Popular",
    "Restaurasaun Independensia", "rendimentu", "Timor-Leste", "Governu")
#: PORTUGUESE, co-official in Timor-Leste and THE LANGUAGE OF ITS LAW -- a genuinely distinctive
#: Asian fact. The Jornal da Republica, the Petroleum Fund Law, the state budget and the audited
#: fund reports are read in Portuguese or not at all, and an Asia desk that crawls only English
#: and Tetum never reads the statute that governs the biggest number in the country.
PORTUGUESE_MARKERS: tuple[str, ...] = (
    "Fundo Petrolifero", "Banco Central de Timor-Leste", "Jornal da Republica",
    "Rendimento Sustentavel Estimado", "Orcamento Geral do Estado", "receitas do petroleo",
    "Restauracao da Independencia", "Consulta Popular", "Proclamacao da Independencia",
    "relatorio trimestral auditado", "Greater Sunrise", "Sexta-feira Santa")


def has_script(text: str, script: str) -> bool:
    """True when `text` carries at least one codepoint of the named script."""
    ranges = _SCRIPTS.get(script)
    if not ranges:
        raise ValueError(f"unknown script {script!r}; known: {sorted(_SCRIPTS)}")
    return any(any(lo <= ord(ch) <= hi for lo, hi in ranges) for ch in str(text))


def has_arabic(text: str) -> bool:
    return has_script(text, "arabic")


def has_thaana(text: str) -> bool:
    return has_script(text, "thaana")


def has_tibetan(text: str) -> bool:
    return has_script(text, "tibetan")


def _flat_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> set[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return {t for terms in rows.values() for t in terms}


def script_terms(script: str, terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    """Every term in the table actually written in one of the three non-Latin scripts."""
    return sorted(t for t in _flat_terms(terminology) if has_script(t, script))


def marker_terms(markers: Iterable[str],
                 terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    """Which of a declared Latin-script marker list the terminology table actually carries."""
    flat = _flat_terms(terminology)
    return [m for m in markers if any(m in t for t in flat)]


def term_count(terminology: Mapping[str, Iterable[str]] | None = None) -> int:
    return len(_flat_terms(terminology))


def languages_present(terminology: Mapping[str, Iterable[str]] | None = None) -> dict[str, int]:
    """HOW MANY TERMS PER LANGUAGE, counted rather than claimed. A pack that says it reads five
    scripts and carries four Thaana words is an English glossary with decoration on it."""
    return {
        "arabic_script": len(script_terms("arabic", terminology)),
        "thaana": len(script_terms("thaana", terminology)),
        "tibetan": len(script_terms("tibetan", terminology)),
        "jawi_markers": len(marker_terms(JAWI_MARKERS, terminology)),
        "malay_rumi": len(marker_terms(MALAY_MARKERS, terminology)),
        "tetum": len(marker_terms(TETUM_MARKERS, terminology)),
        "portuguese": len(marker_terms(PORTUGUESE_MARKERS, terminology)),
    }


def _seq(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(str(v) for v in values)


def source_class(sid: str, label: str, *, layer: str, roots: Iterable[str],
                 queries: Iterable[str], languages: Iterable[str], access_label: str,
                 credibility: str, predictive_state: str, licence: str,
                 jurisdictions: Iterable[str] = (), machine_use_allowed: bool = True,
                 notes: str = "") -> dict[str, Any]:
    """One class of source with the roots a crawler starts from and its three INDEPENDENT labels.

    `queries` are native-script terms, never translations: a miner that searches an English
    phrase on a Dhivehi or Dzongkha ground finds the English corner of it and reports the corner
    as the ground. `machine_use_allowed=False` registers a source whose terms forbid extraction:
    never scraped, never omitted, because omitting it loses the knowledge that the ground exists.
    """
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"source {sid}: layer {layer!r} not one of {list(SOURCE_LAYERS)}")
    if access_label not in ACCESS_LABELS:
        raise ValueError(f"source {sid}: access_label {access_label!r}")
    if credibility not in CREDIBILITY_LABELS:
        raise ValueError(f"source {sid}: credibility {credibility!r}")
    if predictive_state not in PREDICTIVE_STATES:
        raise ValueError(f"source {sid}: predictive_state {predictive_state!r}")
    for code in jurisdictions:
        if code not in JURISDICTIONS:
            raise ValueError(f"source {sid}: {code!r} is not one of {list(JURISDICTIONS)}")
    return {"id": sid, "label": label, "layer": layer, "roots": _seq(roots),
            "queries": _seq(queries), "languages": _seq(languages),
            "jurisdictions": _seq(jurisdictions), "access_label": access_label,
            "credibility": credibility, "predictive_state": predictive_state,
            "machine_use_allowed": bool(machine_use_allowed), "licence": licence, "notes": notes}


def absent_layer(layer: str, reason: str) -> dict[str, Any]:
    """A layer this pack has nothing in ANYWHERE, declared by name with the reason (L1.28a)."""
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"absent layer {layer!r}")
    return {"id": f"absent_{layer}", "label": f"NO SOURCE IN THIS LAYER: {layer}", "layer": layer,
            "roots": (), "queries": (), "languages": (), "jurisdictions": (),
            "access_label": "ACCESS_UNCLEAR", "credibility": "UNKNOWN",
            "predictive_state": "UNTESTED", "machine_use_allowed": False, "licence": "n/a",
            "notes": f"DECLARED ABSENT, NOT BLANK: {reason}"}


def jurisdiction_absence(jurisdiction: str, layer: str, *, reason: str, substitute: str,
                         substitute_root: str) -> dict[str, Any]:
    """A layer ONE jurisdiction has no lawful ground in, with the substitute that stands in.

    THIS IS THE ROW THIS PACK EXISTS TO DEMONSTRATE, and for Afghanistan it may be the most
    valuable output in the whole file. A regional pack can be fully sourced in all ten layers and
    still be blind in one country: Brunei publishes no sovereign-fund holdings, Timor-Leste and
    the Maldives have no domestic economics literature of depth, Bhutan has no retail ecology at
    all, and Afghanistan is missing most layers outright. Averaging those into a regional
    coverage number hides every one of them. So the absence is declared PER JURISDICTION, with a
    REASON that names the missing publication and a SUBSTITUTE that names the lawful ground read
    instead. An absence with a substitute is a measurement and a plan; a padded source list that
    hides it is neither.
    """
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"absent layer {layer!r}")
    if jurisdiction not in JURISDICTIONS:
        raise ValueError(f"jurisdiction {jurisdiction!r} is not one of {list(JURISDICTIONS)}")
    return {"id": f"no_ground_{jurisdiction}_{layer}", "jurisdiction": jurisdiction,
            "layer": layer, "reason": reason, "substitute": substitute,
            "substitute_root": substitute_root,
            "rule": "DECLARED ABSENT WITH A SUBSTITUTE: the layer is not blank, it is empty for "
                    "this jurisdiction and the lawful ground that stands in for it is named"}

# --------------------------------------------------------------------------- terminology
#: FIVE SCRIPTS. An English-only crawl of these five reads none of them.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "brunei_energy": ("minyak dan gas", "gas asli cecair", "pengeluaran minyak mentah",
                      "kilang penapisan", "Pulau Muara Besar", "eksport", "ميڽق دان ݢس",
                      "Jabatan Tenaga", "kontrak jangka panjang", "muatan LNG"),
    "brunei_money": ("dolar Brunei", "Perjanjian Pertukaran Mata Wang", "Autoriti Monetari",
                     "Bank Pusat Brunei Darussalam", "دولار بروني", "بنك ڤوسة",
                     "Agensi Pelaburan Brunei", "Tabung Amanah Pekerja", "sukuk al-ijarah",
                     "rizab antarabangsa"),
    "brunei_state": ("Kementerian Kewangan dan Ekonomi", "Jabatan Perancangan Ekonomi dan "
                     "Statistik", "titah", "warta kerajaan", "Hari Kebangsaan", "كراجاءن",
                     "تيتح", "وارتا كراجاءن", "بروني دارالسلام", "Majlis Mesyuarat Negara"),
    "brunei_calendar": ("Hari Raya Aidilfitri", "هاري راي عيدالفطري", "هاري راي عيدالاضحى",
                        "مولود الرسول", "اسرا معراج", "نزول القرءان", "Tahun Baru Cina",
                        "Awal Tahun Hijrah"),
    "timor_fund": ("Fundo Petrolifero", "Fundu Petroliferu", "Rendimento Sustentavel Estimado",
                   "relatorio trimestral auditado", "receitas do petroleo", "levantamentos",
                   "Banco Central de Timor-Leste", "Banku Sentral", "rendimentu"),
    "timor_state": ("Orcamento Geral do Estado", "Jornal da Republica", "Governu", "osan",
                    "folin", "loron", "Timor-Leste", "Consulta Popular", "Konsulta Popular",
                    "Restauracao da Independencia", "Restaurasaun Independensia",
                    "Proclamacao da Independencia", "Sexta-feira Santa"),
    "timor_energy": ("Bayu-Undan", "Greater Sunrise", "Tasi Mane", "ANPM", "Timor GAP",
                     "producao de petroleo", "gasoduto"),
    "maldives_tourism": ("ފަތުރުވެރިކަން", "ޓޫރިސްޓުން", "ރިޒޯޓް", "ގެސްޓްހައުސް",
                         "ބެޑް ނައިޓް", "އެރައިވަލް", "velana", "bed nights"),
    "maldives_money": ("ރުފިޔާ", "ޑޮލަރު", "ރިޒާވް", "މަރުކަޒީ ބޭންކް",
                       "މޯލްޑިވްސް މަނިޓަރީ އޮތޯރިޓީ", "ދަރަނި", "ބަޖެޓް", "ސުކޫކް",
                       "parallel premium", "usable reserves"),
    "maldives_state": ("ދިވެހިރާއްޖެ", "ގެޒެޓް", "މަޖިލިސް", "މިނިވަން ދުވަސް", "އީދު",
                       "ސަރުކާރު"),
    "bhutan_power": ("འབྲུག་ཡུལ།", "གློག་ཤུགས།", "ཆུ་གློག", "ཚོང་ལས།", "Druk Green",
                     "Mangdechhu", "Punatsangchhu", "Tala", "Chukha", "monsoon generation",
                     "winter import"),
    "bhutan_money": ("དངུལ་ཀྲམ།", "དངུལ་ཁང་།", "rupee reserves", "ngultrum parity",
                     "Royal Monetary Authority", "Druk Holding and Investments"),
    "bhutan_calendar": ("ལོ་གསར།", "རྒྱལ་ཡོངས་དུས་ཆེན།", "Thrue Bab", "Thimphu Tshechu",
                        "Pangrizampa", "Nyilo"),
    "afghan_money": ("د افغانستان بانک", "افغانۍ", "بانک مرکزی", "افغانی", "لیلام اسعار",
                     "ذخایر ارزی", "صرافی", "سرای شهزاده", "حواله"),
    "afghan_trade": ("زغال سنگ", "ډبره سکاره", "مس عینک", "گمرک", "ګمرک", "صادرات", "واردات",
                     "سوداګري", "تورخم", "حیرتان", "لیتیم"),
    "afghan_rural": ("تریاک", "کوکنار", "کرنه", "گندم", "نوروز", "سال مالی", "حمل"),
    "regional_cross": ("SAARC", "ASEAN", "mirror customs", "single factor", "par link",
                       "dollarisation", "closure breadth"),
}

# --------------------------------------------------------------------------- sources
SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    # ---- official
    source_class(
        "mar_bn_bdcb", "Brunei Darussalam Central Bank: monetary and financial statistics, the "
                       "currency board and the Currency Interchangeability Agreement, notices",
        layer="official", jurisdictions=("bn",),
        roots=("https://www.bdcb.gov.bn", "https://www.bdcb.gov.bn/statistics"),
        queries=("Bank Pusat Brunei Darussalam statistik", "dolar Brunei", "بنك ڤوسة",
                 "Perjanjian Pertukaran Mata Wang", "rizab antarabangsa", "sukuk al-ijarah"),
        languages=("ms", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the currency board's own publisher; there is no policy decision here to mine"),
    source_class(
        "mar_bn_deps", "Department of Economic Planning and Statistics (DEPS), Ministry of "
                       "Finance and Economy: GDP with oil and gas broken out, CPI, trade",
        layer="official", jurisdictions=("bn",),
        roots=("https://deps.mofe.gov.bn", "https://deps.mofe.gov.bn/SitePages/National%20"
                                            "Accounts.aspx"),
        queries=("Jabatan Perancangan Ekonomi dan Statistik", "Kementerian Kewangan dan Ekonomi",
                 "minyak dan gas", "eksport", "كراجاءن"),
        languages=("ms", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the non-oil economy is small enough that the headline is a production series"),
    source_class(
        "mar_bn_energy", "Energy Department, Prime Minister's Office: crude, condensate and LNG "
                         "production and export volumes; the Hengyi product line from 2019",
        layer="official", jurisdictions=("bn",),
        roots=("https://www.energy.gov.bn", "https://www.agc.gov.bn"),
        queries=("Jabatan Tenaga", "pengeluaran minyak mentah", "gas asli cecair",
                 "kilang penapisan", "ميڽق دان ݢس", "وارتا كراجاءن", "warta kerajaan"),
        languages=("ms", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="paired with the Attorney General's Chambers gazette, where the concession and "
              "energy instruments are actually published"),
    source_class(
        "mar_tl_bctl", "Banco Central de Timor-Leste: THE PETROLEUM FUND QUARTERLY AUDITED "
                       "REPORTS, balance of payments, the dollarised monetary statistics",
        layer="official", jurisdictions=("tl",),
        roots=("https://www.bancocentral.tl",
               "https://www.bancocentral.tl/en/go/petroleum-fund-quarterly-reports"),
        queries=("Fundo Petrolifero relatorio trimestral auditado",
                 "Rendimento Sustentavel Estimado", "receitas do petroleo", "levantamentos",
                 "Banku Sentral", "Fundu Petroliferu"),
        languages=("pt", "tet", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE PACK'S BEST DISCLOSURE. Holdings, returns, receipts and withdrawals for a "
              "fund that is the entire state's balance sheet"),
    source_class(
        "mar_tl_state", "INETL (statistics), ANPM (petroleum regulator) and the Jornal da "
                        "Republica: CPI, trade, production and the law itself",
        layer="official", jurisdictions=("tl",),
        roots=("https://inetl-ip.gov.tl", "https://www.anpm.tl", "http://www.jornal.gov.tl"),
        queries=("Orcamento Geral do Estado", "Jornal da Republica", "Bayu-Undan",
                 "Greater Sunrise", "Tasi Mane", "producao de petroleo", "Governu", "folin"),
        languages=("pt", "tet", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="PORTUGUESE IS THE LANGUAGE OF THE LAW HERE. The Petroleum Fund Law, the budget "
              "and the Greater Sunrise instruments are read in it or not at all"),
    source_class(
        "mar_mv_tourism", "Ministry of Tourism, Maldives: DAILY arrivals by nationality and by "
                          "accommodation type, plus the monthly statistical release",
        layer="official", jurisdictions=("mv",),
        roots=("https://www.tourism.gov.mv", "https://www.tourism.gov.mv/statistics"),
        queries=("ފަތުރުވެރިކަން", "ޓޫރިސްޓުން", "ރިޒޯޓް", "ގެސްޓްހައުސް", "ބެޑް ނައިޓް"),
        languages=("dv", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE HIGHEST-FREQUENCY PUBLIC REAL-ACTIVITY SERIES IN THIS PACK: a daily physical "
              "count, split by source economy, with a one-day lag"),
    source_class(
        "mar_mv_mma", "Maldives Monetary Authority and the National Bureau of Statistics: gross "
                      "and usable reserves, money, the rufiyaa rate, GDP and CPI",
        layer="official", jurisdictions=("mv",),
        roots=("https://www.mma.gov.mv", "https://statisticsmaldives.gov.mv",
               "https://www.finance.gov.mv", "https://www.gazette.gov.mv"),
        queries=("ރުފިޔާ", "ރިޒާވް", "މޯލްޑިވްސް މަނިޓަރީ އޮތޯރިޓީ", "ދަރަނި", "ބަޖެޓް",
                 "ގެޒެޓް", "ސުކޫކް"),
        languages=("dv", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the DEFENCE of the peg; the gross-versus-usable gap is where the stress lives"),
    source_class(
        "mar_bt_rma", "Royal Monetary Authority of Bhutan and the National Statistics Bureau: "
                      "the RUPEE reserve split, money, trade with India, national accounts",
        layer="official", jurisdictions=("bt",),
        roots=("https://www.rma.org.bt", "https://www.nsb.gov.bt"),
        queries=("དངུལ་ཀྲམ།", "དངུལ་ཁང་།", "འབྲུག་ཡུལ།", "ཚོང་ལས།", "rupee reserves",
                 "ngultrum parity"),
        languages=("dz", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the rupee/convertible reserve split is unusual and is the number that binds"),
    source_class(
        "mar_bt_dgpc", "Druk Green Power Corporation and Druk Holding and Investments: "
                       "generation and export volumes by plant, and the state holding's accounts",
        layer="official", jurisdictions=("bt",),
        roots=("https://www.dgpc.bt", "https://www.dhi.bt"),
        queries=("གློག་ཤུགས།", "ཆུ་གློག", "Druk Green", "Mangdechhu", "Punatsangchhu",
                 "monsoon generation", "winter import"),
        languages=("dz", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the monsoon cycle in numbers, including the winter months in which the sign flips"),
    source_class(
        "mar_af_dab", "Da Afghanistan Bank and the National Statistics and Information "
                      "Authority: FX auction announcements and results, the reference rate, and "
                      "whatever NSIA still publishes",
        layer="official", jurisdictions=("af",),
        roots=("https://www.dab.gov.af", "https://nsia.gov.af"),
        queries=("د افغانستان بانک", "لیلام اسعار", "ذخایر ارزی", "افغانی", "افغانۍ",
                 "بانک مرکزی"),
        languages=("fa-AF", "ps", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="PUBLICATION HAS NARROWED SEVERELY SINCE 2021 and availability from outside the "
              "country is intermittent. Read, never transacted in; an unread auction is "
              "UNMEASURED, not zero"),
    # ---- institutional
    source_class(
        "mar_imf_wb", "IMF Article IV and staff reports, and the WORLD BANK AFGHANISTAN "
                      "ECONOMIC MONITOR -- the substitute national accounts for af",
        layer="institutional", jurisdictions=("bn", "tl", "mv", "bt", "af"),
        roots=("https://www.imf.org/en/Countries", "https://www.worldbank.org/en/country/"
                                                   "afghanistan/publication/"
                                                   "afghanistan-economic-monitor"),
        queries=("Article IV Brunei Darussalam", "Article IV Maldives reserves",
                 "Afghanistan Economic Monitor", "Timor-Leste petroleum wealth",
                 "Bhutan hydropower debt sustainability"),
        languages=("en",), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the ONLY external-asset aggregate that covers Brunei's sovereign wealth at all, "
              "and the substitute for Afghan national accounts"),
    source_class(
        "mar_un", "UNAMA, OCHA, WFP and the UN's own disclosed US-dollar cash shipments; UNODC's "
                  "published Afghanistan opium surveys",
        layer="institutional", jurisdictions=("af",),
        roots=("https://unama.unmissions.org", "https://www.unocha.org/afghanistan",
               "https://www.unodc.org/unodc/en/crop-monitoring/index.html"),
        queries=("UNAMA cash shipment", "OCHA Afghanistan humanitarian", "UNODC opium survey",
                 "تریاک", "کوکنار", "گندم"),
        languages=("en", "fa-AF", "ps"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE LAWFUL SUBSTITUTE FOR MOST OF AFGHANISTAN'S MISSING LAYERS, and the source of "
              "the dated, quantified opium collapse recorded in NO_EXECUTABLE_LEG"),
    source_class(
        "mar_adb_regional", "ADB country pages and key indicators, ASEAN statistics and the "
                            "SAARC secretariat -- the regional aggregators",
        layer="institutional", jurisdictions=("bn", "tl", "mv", "bt", "af"),
        roots=("https://www.adb.org/countries", "https://www.aseanstats.org",
               "https://www.saarc-sec.org"),
        queries=("ADB Bhutan key indicators", "ASEAN statistics Brunei Timor-Leste",
                 "SAARC Maldives Bhutan Afghanistan", "Timor-Leste ASEAN accession"),
        languages=("en",), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the only place the ASEAN half and the SAARC half of this pack are ever tabulated "
              "side by side, which is itself the pack's organising problem"),
    source_class(
        "mar_iea_eia", "IEA and EIA gas and oil trade data; the Japanese and Korean LNG import "
                       "statistics that are the other end of Brunei's contracts",
        layer="institutional", jurisdictions=("bn",),
        roots=("https://www.iea.org/data-and-statistics", "https://www.eia.gov/international/"),
        queries=("LNG imports by origin Japan Korea", "Brunei LNG exports",
                 "kontrak jangka panjang", "muatan LNG"),
        languages=("en", "ms"), access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free with attribution; some tables licensed",
        notes="THE BUYER'S CUSTOMS TABLE IS THE MIRROR STATISTIC FOR BRUNEI'S CARGOES, exactly "
              "as Pakistan's is for Afghanistan's coal"),
    # ---- academic
    source_class(
        "mar_academic", "Universiti Brunei Darussalam, the Royal University of Bhutan, the "
                        "Maldives National University, and OpenAlex/CORE for everything else",
        layer="academic", jurisdictions=("bn", "bt", "mv"),
        roots=("https://openalex.org", "https://core.ac.uk", "https://www.ubd.edu.bn",
               "https://www.rub.edu.bt"),
        queries=("Brunei resource curse minyak dan gas", "Bhutan hydropower debt ཆུ་གློག",
                 "Maldives tourism elasticity ފަތުރުވެރިކަން", "Timor-Leste Dutch disease "
                 "Fundo Petrolifero", "Afghanistan mirror statistics گمرک"),
        languages=("en", "ms", "dz", "dv", "pt"), access_label="OPEN_DATA",
        credibility="RELIABLE", predictive_state="UNTESTED", licence="CC-BY / CC0 for OpenAlex",
        notes="THIN BY CONSTRUCTION. See NO_LAWFUL_GROUND for tl, mv and af, where there is no "
              "domestic economics literature of depth and the substitute is named"),
    # ---- practitioner
    source_class(
        "mar_lng_practitioner", "The LNG and oil price-reporting agencies and the Asian gas "
                                "trade press -- REGISTERED, NEVER SCRAPED",
        layer="practitioner", jurisdictions=("bn",),
        roots=("https://www.argusmedia.com", "https://www.spglobal.com/commodityinsights"),
        queries=("JKM assessment Northeast Asia", "Brunei LNG term contract renewal",
                 "kontrak jangka panjang", "muatan LNG"),
        languages=("en", "ms"), access_label="LICENSED", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="proprietary; terms forbid machine extraction",
        machine_use_allowed=False,
        notes="machine_use_allowed=False. The assessments are the market's reference and the "
              "desk may not extract them; the ground is registered so the knowledge that it "
              "exists is not lost, and the free IEA/EIA volumes stand in"),
    source_class(
        "mar_travel_practitioner", "The Maldivian resort and travel trade: operator capacity "
                                   "announcements, charter schedules and the hotel-rate trade "
                                   "press",
        layer="practitioner", jurisdictions=("mv",),
        roots=("https://corporatemaldives.com", "https://maldives.net.mv"),
        queries=("ރިޒޯޓް", "ބެޑް ނައިޓް", "charter capacity Male", "resort occupancy Maldives"),
        languages=("dv", "en"), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="free to read; republication restricted",
        notes="KEPT AT LOW WEIGHT, NEVER DROPPED: the trade press front-runs the ministry's own "
              "arrivals series on capacity, and a claim that looks promotional is still a dated "
              "testable claim"),
    source_class(
        "mar_af_practitioner", "Afghan trade and transit practitioners: chambers of commerce, "
                               "the Torkham and Chaman transit operators, coal traders' reports",
        layer="practitioner", jurisdictions=("af",),
        roots=("https://acci.org.af", "https://pajhwok.com/category/business/"),
        queries=("زغال سنگ صادرات", "ډبره سکاره", "تورخم", "حیرتان", "سوداګري", "گمرک"),
        languages=("fa-AF", "ps", "en"), access_label="PUBLIC", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="low weight and kept: trader reports are the only near-real-time read on border "
              "volumes and they are routinely contradicted by the mirror customs tables, which "
              "is itself a useful signal about which months are disputed"),
    # ---- retail_ecology
    source_class(
        "mar_money_changers", "THE INFORMAL FX MARKETS, which are the only retail ecology these "
                              "five have: Sarai Shahzada in Kabul, the Maldivian parallel dollar "
                              "market, Brunei's licensed money-changers at the SGD par, and the "
                              "border rupee trade in Bhutan",
        layer="retail_ecology", jurisdictions=("af", "mv", "bn", "bt"),
        roots=("https://pajhwok.com", "https://mihaaru.com", "https://www.dab.gov.af"),
        queries=("صرافی", "سرای شهزاده", "حواله", "ޑޮލަރު", "parallel premium",
                 "dolar Brunei", "rupee reserves"),
        languages=("fa-AF", "ps", "dv", "ms", "en"), access_label="PUBLIC_SOCIAL",
        credibility="UNRELIABLE", predictive_state="UNTESTED", licence="free, public reporting",
        notes="THERE IS NO LICENSED RETAIL MARGIN INDUSTRY IN ANY OF THE FIVE -- no broker, no "
              "leverage regime, no margin statistics. The money-changer market is what a retail "
              "ecology actually looks like here, its quotes are reported openly, and the "
              "PARALLEL PREMIUM it prints is the single most informative retail number in the "
              "pack. Low weight, kept, never traded"),
    # ---- app_ecosystem
    source_class(
        "mar_apps", "The payment and booking apps: BIBD NEXGEN in Brunei, BML and the resort "
                    "booking platforms in the Maldives, mBoB in Bhutan, BNCTL and mobile wallets "
                    "in Timor-Leste, and HesabPay and the hawala networks in Afghanistan",
        layer="app_ecosystem", jurisdictions=("bn", "mv", "bt", "tl", "af"),
        roots=("https://play.google.com/store", "https://apps.apple.com"),
        queries=("BIBD NEXGEN", "mBoB Bhutan", "BML mobile ދިވެހިރާއްޖެ", "HesabPay حواله",
                 "ގެސްޓްހައުސް booking", "osan"),
        languages=("ms", "dv", "dz", "tet", "fa-AF", "en"), access_label="PUBLIC_WITH_TERMS",
        credibility="UNRELIABLE", predictive_state="UNTESTED",
        licence="store listings public; app content under the operators' terms",
        notes="release notes and store rankings are a cheap dated read on payment-system change "
              "in economies with no other high-frequency financial series"),
    # ---- media
    source_class(
        "mar_media_bn_tl", "Borneo Bulletin, Media Permata (Malay, with Jawi mastheads) and RTB "
                           "in Brunei; Tempo Timor, STL and the Portuguese-language press in "
                           "Timor-Leste",
        layer="media", jurisdictions=("bn", "tl"),
        roots=("https://borneobulletin.com.bn", "https://www.rtb.gov.bn",
               "https://tempotimor.com"),
        queries=("تيتح", "بروني دارالسلام", "warta kerajaan", "Hari Kebangsaan",
                 "Fundo Petrolifero", "Governu", "Konsulta Popular"),
        languages=("ms", "pt", "tet", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free to read",
        notes="the titah is published verbatim and IS the policy announcement in Brunei"),
    source_class(
        "mar_media_mv_bt", "Mihaaru, Sun.mv and Adhadhu in Dhivehi; Kuensel and BBS in Bhutan",
        layer="media", jurisdictions=("mv", "bt"),
        roots=("https://mihaaru.com", "https://sun.mv", "https://kuenselonline.com",
               "http://www.bbs.bt"),
        queries=("ދިވެހިރާއްޖެ", "ރުފިޔާ", "ރިޒާވް", "ފަތުރުވެރިކަން", "འབྲུག་ཡུལ།",
                 "ལོ་གསར།", "rupee reserves"),
        languages=("dv", "dz", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free to read",
        notes="THE DHIVEHI PRESS CARRIES THE PARALLEL RATE the MMA does not publish; an "
              "English-only crawl of the Maldives misses it entirely"),
    source_class(
        "mar_media_af", "TOLOnews, Ariana News and Hasht-e Subh in Dari and Pashto",
        layer="media", jurisdictions=("af",),
        roots=("https://tolonews.com", "https://www.ariananews.af", "https://8am.media"),
        queries=("افغانی", "لیلام اسعار", "زغال سنگ", "گمرک", "صرافی", "ډبره سکاره", "نوروز"),
        languages=("fa-AF", "ps", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free to read",
        notes="reporting conditions have narrowed sharply; several outlets publish from exile, "
              "which is a fact about the source and is carried rather than used to discard it"),
    # ---- archive
    source_class(
        "mar_archive", "The gazettes and their archives: agc.gov.bn, jornal.gov.tl, "
                       "gazette.gov.mv, the Bhutanese Cabinet's holiday lists, plus the Wayback "
                       "Machine and the UN document archive for everything Afghanistan has "
                       "taken down",
        layer="archive", jurisdictions=("bn", "tl", "mv", "bt", "af"),
        roots=("https://web.archive.org", "https://www.agc.gov.bn", "http://www.jornal.gov.tl",
               "https://www.gazette.gov.mv", "https://digitallibrary.un.org"),
        queries=("وارتا كراجاءن", "Jornal da Republica arquivo", "ގެޒެޓް", "warta kerajaan",
                 "Pangrizampa", "UNAMA archive"),
        languages=("ms", "pt", "dv", "dz", "en"), access_label="PUBLIC_ARCHIVE",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="THE POINT-IN-TIME LAYER. Several of these sites overwrite in place and one "
              "jurisdiction has removed years of material; the archive is the only vintage"),
    # ---- physical_economy
    source_class(
        "mar_physical", "MIRROR CUSTOMS AND PHYSICAL COUNTS: Pakistan (PBS/FBR), Iran (IRICA), "
                        "China (GACC) and Uzbekistan for Afghan trade; Japanese and Korean LNG "
                        "imports for Brunei; Velana airport movements for the Maldives; Indian "
                        "grid data for Bhutan's exports",
        layer="physical_economy", jurisdictions=("af", "bn", "mv", "bt"),
        roots=("http://stats.customs.gov.cn", "https://www.pbs.gov.pk",
               "https://www.irica.ir", "https://stat.uz", "https://npp.gov.in"),
        queries=("گمرک صادرات افغانستان", "زغال سنگ پاکستان", "ډبره سکاره", "حیرتان",
                 "LNG imports by origin", "Velana aircraft movements", "gloG ཆུ་གློག export"),
        languages=("fa-AF", "ps", "en", "zh"), access_label="OPEN_DATA",
        credibility="AUTHORITATIVE", predictive_state="UNTESTED", licence="free, public",
        notes="THE MOST IMPORTANT LAYER IN THIS PACK. A partner's customs table is a published "
              "statistic ABOUT THE PARTNER, and it is how Afghan coal and mineral exports are "
              "counted at all -- the same technique the `caucasus_central_asia` pack uses for "
              "Turkmen gas, and the reason these two packs interact"),
    # ---- source_graph
    source_class(
        "mar_source_graph", "CITATION-FOLLOWING: every World Bank Economic Monitor, IMF Article "
                            "IV, UNODC survey and Petroleum Fund report footnotes a table this "
                            "desk has not read yet; following the footnote is how this pack's "
                            "source list grows without anybody guessing a hostname",
        layer="source_graph", jurisdictions=("bn", "tl", "mv", "bt", "af"),
        roots=("https://openalex.org", "https://www.worldbank.org/en/research",
               "https://digitallibrary.un.org"),
        queries=("according to DAB auction data", "segundo o relatorio trimestral auditado",
                 "به اساس ارقام گمرکی", "as reported by the Ministry of Tourism",
                 "sources cited in Afghanistan Economic Monitor"),
        languages=("en", "pt", "fa-AF"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE EXPANSION EDGE, and in this pack it is load-bearing: for Afghanistan the "
              "footnote IS the data-discovery mechanism"),
)

#: NO PACK-LEVEL LAYER IS BLANK -- all ten are sourced regionally, which is the honest regional
#: statement. It is NOT the same as saying every jurisdiction is covered in every layer, and the
#: per-jurisdiction holes are in NO_LAWFUL_GROUND below with their substitutes.
LAYER_ABSENCES: dict[str, str] = {}

#: THE MEASURED REFUSAL, PER JURISDICTION. Afghanistan carries most of it; Brunei's sovereign
#: fund and Bhutan's retail ecology carry the rest. Each row names the missing publication AND
#: the lawful ground read instead, so the absence is a plan rather than a shrug (L1.28a).
NO_LAWFUL_GROUND: tuple[dict[str, Any], ...] = (
    jurisdiction_absence(
        "bn", "institutional",
        reason="THE BRUNEI INVESTMENT AGENCY PUBLISHES NOTHING -- no holdings, no size, no "
               "return, no annual report. The sovereign wealth that is the whole point of the "
               "economy is undisclosed, and so is the Tabung Amanah Pekerja provident fund's "
               "portfolio. THAT OPACITY IS THE MEASUREMENT, not a gap in this pack's reading",
        substitute="the IMF Article IV external-asset aggregate and the balance-of-payments "
                   "financial account, which bound the fund from outside without disclosing it",
        substitute_root="https://www.imf.org/en/Countries/BRN"),
    jurisdiction_absence(
        "bn", "retail_ecology",
        reason="there is NO STOCK EXCHANGE, no licensed retail margin industry, no leverage "
               "regime and no margin statistics in Brunei; domestic savings run through banks, "
               "takaful and two undisclosed funds",
        substitute="the licensed money-changers quoting the BND/SGD par, and Singapore's own "
                   "retail ecology one link up, which the `sg` pack owns",
        substitute_root="https://www.bdcb.gov.bn"),
    jurisdiction_absence(
        "tl", "academic",
        reason="there is no domestic academic economics literature of any depth and no "
               "university repository a crawler can usefully reach; what exists on Timor-Leste's "
               "economy is written abroad, mostly in English and Portuguese",
        substitute="OpenAlex and CORE for the external literature, plus the Petroleum Fund's own "
                   "Investment Advisory Board minutes, which are the closest thing to a "
                   "domestic analytical record",
        substitute_root="https://openalex.org"),
    jurisdiction_absence(
        "tl", "retail_ecology",
        reason="a dollarised economy with no securities market, no domestic currency to trade "
               "and no retail brokerage; there is nothing for a retail ecology to form around",
        substitute="the Petroleum Fund's published allocation IS the population's financial "
                   "exposure, disclosed quarterly -- an unusually complete substitute",
        substitute_root="https://www.bancocentral.tl"),
    jurisdiction_absence(
        "mv", "academic",
        reason="no domestic economics literature of depth; the Maldives National University "
               "publishes little that a macro miner can use and there is no working-paper series",
        substitute="IMF Article IV and World Bank country economic updates, which carry the "
                   "reserve and debt analysis that a domestic literature would have",
        substitute_root="https://www.imf.org/en/Countries/MDV"),
    jurisdiction_absence(
        "bt", "retail_ecology",
        reason="capital controls, no convertible currency to speculate in, a session-traded "
               "exchange with a couple of dozen issuers and no margin industry: Bhutan's retail "
               "financial ecology does not exist in any form a miner can read",
        substitute="the cross-border rupee trade and the RMA's own household credit statistics, "
                   "which are what household financial behaviour looks like here",
        substitute_root="https://www.rma.org.bt"),
    jurisdiction_absence(
        "af", "official",
        reason="NSIA's statistical publication has narrowed severely since 2021, no regular "
               "national accounts or trade tables are issued, and the central bank's reserves "
               "are frozen abroad so the reserve series has no meaning it used to have",
        substitute="the World Bank Afghanistan Economic Monitor as substitute national accounts, "
                   "DAB's published FX auctions for the monetary side, and MIRROR CUSTOMS from "
                   "Pakistan, Iran, China and Uzbekistan for trade",
        substitute_root="https://www.worldbank.org/en/country/afghanistan"),
    jurisdiction_absence(
        "af", "institutional",
        reason="there is no exchange, no clearer, no listed issuer, no functioning correspondent "
               "banking and no industry association publishing data; the de facto authorities "
               "are not recognised by most states, so the normal institutional layer is absent",
        substitute="UN agency reporting (UNAMA, OCHA, WFP), the UN's disclosed cash shipments, "
                   "and UNODC's published surveys",
        substitute_root="https://unama.unmissions.org"),
    jurisdiction_absence(
        "af", "academic",
        reason="the domestic university system's economics output has effectively stopped and "
               "there is no reachable repository; what exists is written abroad",
        substitute="OpenAlex and CORE, plus the World Bank's and UNODC's own method annexes, "
                   "which document how the substitute statistics are constructed",
        substitute_root="https://core.ac.uk"),
    jurisdiction_absence(
        "af", "app_ecosystem",
        reason="the banking system is largely disconnected from international correspondents, "
               "card rails barely function and most payment activity is cash or hawala, which "
               "leaves almost no app telemetry to read",
        substitute="HesabPay and the humanitarian cash-transfer programmes' own published "
                   "reporting, which is where digital payment volume actually shows up",
        substitute_root="https://www.unocha.org/afghanistan"),
    jurisdiction_absence(
        "af", "physical_economy",
        reason="Afghanistan publishes no port, freight, customs or energy throughput series of "
               "its own; the border crossings are counted by the countries on the other side",
        substitute="MIRROR CUSTOMS at Torkham, Chaman, Hairatan and Islam Qala from Pakistan, "
                   "Iran, China and Uzbekistan -- the pack's clearest worked example of lawful "
                   "ground substituting for an absent one",
        substitute_root="https://www.pbs.gov.pk"),
    jurisdiction_absence(
        "mv", "physical_economy",
        reason="no freight, port or energy throughput series is published at a usable frequency; "
               "an atoll economy's physical activity is arrivals and bed-nights and little else",
        substitute="the DAILY arrivals bulletin itself and Velana airport movement counts, which "
                   "together are a better physical series than most economies publish",
        substitute_root="https://www.tourism.gov.mv/statistics"),
    jurisdiction_absence(
        "bt", "app_ecosystem",
        reason="a small domestic app market with no public telemetry and no rankings deep enough "
               "to read; mBoB is essentially the only relevant application",
        substitute="the RMA's own payment-system statistics, which publish digital transaction "
                   "volumes directly",
        substitute_root="https://www.rma.org.bt"),
    jurisdiction_absence(
        "tl", "app_ecosystem",
        reason="very low smartphone-based financial penetration and no published telemetry; the "
               "payment system is cash and bank branches",
        substitute="BCTL's payment-system and financial-inclusion reporting",
        substitute_root="https://www.bancocentral.tl"),
)

#: NATIVE QUERY TERRITORIES: what the deep-forest miner actually runs, per layer, across five
#: scripts. Three or more per layer for every layer, and every layer carries at least one
#: non-Latin script.
QUERY_TERRITORIES: dict[str, tuple[str, ...]] = {
    "official": ("Jabatan Perancangan Ekonomi dan Statistik minyak dan gas", "وارتا كراجاءن",
                 "Fundo Petrolifero relatorio trimestral auditado", "ފަތުރުވެރިކަން ތަފާސްހިސާބު",
                 "ރިޒާވް މޯލްޑިވްސް މަނިޓަރީ އޮތޯރިޓީ", "དངུལ་ཀྲམ། rupee reserves",
                 "د افغانستان بانک لیلام اسعار", "Orcamento Geral do Estado"),
    "institutional": ("Article IV Maldives usable reserves", "Afghanistan Economic Monitor",
                      "UNODC opium survey تریاک", "ADB Bhutan hydropower ཆུ་གློག",
                      "ASEAN statistics Timor-Leste accession", "Agensi Pelaburan Brunei"),
    "academic": ("Brunei resource curse minyak dan gas", "Bhutan hydro debt འབྲུག་ཡུལ།",
                 "Maldives tourism elasticity ފަތުރުވެރިކަން",
                 "Timor-Leste Dutch disease Fundo Petrolifero",
                 "Afghanistan mirror statistics گمرک"),
    "practitioner": ("kontrak jangka panjang LNG Brunei", "JKM term contract renewal",
                     "ރިޒޯޓް occupancy forecast", "زغال سنگ صادرات پاکستان",
                     "Druk Green generation forecast ཆུ་གློག"),
    "retail_ecology": ("صرافی سرای شهزاده نرخ", "حواله افغانی", "ޑޮލަރު ބާޒާރު",
                       "dolar Brunei penukar wang", "rupee shortage Bhutan border"),
    "app_ecosystem": ("BIBD NEXGEN kemaskini", "mBoB འབྲུག་ཡུལ།", "BML ދިވެހިރާއްޖެ",
                      "HesabPay حواله", "osan mobile Timor-Leste"),
    "media": ("تيتح Hari Kebangsaan", "Jornal da Republica Governu", "ރުފިޔާ ދަރަނި",
              "ލޯނު ސުކޫކް", "ལོ་གསར། Kuensel", "افغانی لیلام اسعار TOLOnews",
              "ډبره سکاره سوداګري"),
    "archive": ("وارتا كراجاءن arkib", "Jornal da Republica arquivo", "ގެޒެޓް އާކައިވް",
                "Pangrizampa holiday list archive", "UNAMA archive Afghanistan"),
    "physical_economy": ("گمرک صادرات افغانستان زغال سنگ", "ډبره سکاره تورخم",
                         "LNG imports by origin Japan Korea", "Velana aircraft movements",
                         "ཆུ་གློག export India grid", "muatan LNG Lumut"),
    "source_graph": ("according to DAB auction data", "به اساس ارقام گمرکی",
                     "segundo o relatorio trimestral auditado",
                     "ministry of tourism daily arrivals cited",
                     "sources cited Afghanistan Economic Monitor"),
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


def jurisdiction_coverage() -> dict[str, dict[str, Any]]:
    """PER JURISDICTION, what this pack actually reads and what it has declared missing. The
    regional coverage number is an average and averages are how a blind country hides."""
    out: dict[str, dict[str, Any]] = {}
    for code in JURISDICTIONS:
        sourced = sorted({str(s["layer"]) for s in SOURCE_CLASSES
                          if code in tuple(s.get("jurisdictions") or ())})
        missing = sorted({str(r["layer"]) for r in NO_LAWFUL_GROUND if r["jurisdiction"] == code})
        out[code] = {"layers_sourced": tuple(sourced), "n_sourced": len(sourced),
                     "no_lawful_ground": tuple(missing), "n_absent": len(missing),
                     "actors": sum(1 for a in ACTORS if code in a.get("jurisdictions", ())),
                     "domains": sum(1 for d in DOMAINS if code in d.get("jurisdictions", ()))}
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
            "no_lawful_ground": len(NO_LAWFUL_GROUND),
            "query_territories": {k: len(v) for k, v in QUERY_TERRITORIES.items()},
            "rule": "ten layers, each carrying a source or named ABSENT with a reason; the "
                    "PER-JURISDICTION holes are in NO_LAWFUL_GROUND with a named lawful "
                    "substitute apiece, because a regional average hides a blind country; "
                    "fringe and unreliable PUBLIC material is kept at low weight and never "
                    "dropped; a source whose terms forbid machine extraction is registered "
                    "machine_use_allowed=false, never scraped and never omitted"}

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "Maldives daily tourist arrivals by nationality",
     "source": "Ministry of Tourism, Maldives", "coverage": "2011 onward, daily",
     "frequency": "daily", "publication_lag_days": 1.0, "revisions": "revised into the monthly",
     "licence": "free, public", "history_from": "2011-01", "pit_feasible": True,
     "assets": ("USDINR", "XBRUSD", "US500"),
     "mechanism_families": ("physical_flow", "high_frequency_proxy", "seasonality"),
     "how_to_fetch": "tourism.gov.mv/statistics -- the daily bulletin PDF and the monthly XLSX; "
                     "take the by-nationality split, not the headline, and archive each day's "
                     "bulletin because the site republishes the month over it"},
    {"name": "Maldives monthly tourism statistics: bed-nights, occupancy, average stay",
     "source": "Ministry of Tourism / National Bureau of Statistics",
     "coverage": "1990s onward, monthly", "frequency": "monthly", "publication_lag_days": 20.0,
     "revisions": "occasional", "licence": "free, public", "history_from": "1995-01",
     "pit_feasible": True, "assets": ("USDINR", "US500", "XBRUSD"),
     "mechanism_families": ("capacity", "seasonality"),
     "how_to_fetch": "statisticsmaldives.gov.mv tourism tables and the ministry's monthly "
                     "release; the resort/guesthouse capacity series beside it is the supply leg"},
    {"name": "MMA gross and usable reserves and the rufiyaa rate",
     "source": "Maldives Monetary Authority", "coverage": "2000s onward, monthly",
     "frequency": "monthly", "publication_lag_days": 30.0,
     "revisions": "revised; the USABLE definition has changed", "licence": "free, public",
     "history_from": "2004-01", "pit_feasible": False,
     "assets": ("USDINR", "XAUUSD", "US500"),
     "mechanism_families": ("reserve_stress", "band_state"),
     "how_to_fetch": "mma.gov.mv statistics portal, monthly monetary survey XLSX; splice "
                     "carefully across the usable-reserve definition change or you measure it"},
    {"name": "Maldives external debt and maturity profile including the 2026 sukuk",
     "source": "Ministry of Finance, Maldives", "coverage": "2015 onward, quarterly",
     "frequency": "quarterly", "publication_lag_days": 60.0, "revisions": "restated",
     "licence": "free, public", "history_from": "2015-Q1", "pit_feasible": False,
     "assets": ("USDINR", "XAUUSD", "US500"),
     "mechanism_families": ("credit_event", "regime_break"),
     "how_to_fetch": "finance.gov.mv/publications quarterly debt bulletin; the offshore price of "
                     "the sovereign's own sukuk is the market's reading and is NOT in here"},
    {"name": "Timor-Leste Petroleum Fund quarterly audited report",
     "source": "Banco Central de Timor-Leste", "coverage": "2005 onward, quarterly",
     "frequency": "quarterly", "publication_lag_days": 45.0,
     "revisions": "the audited report can restate the unaudited", "licence": "free, public",
     "history_from": "2005-Q4", "pit_feasible": True,
     "assets": ("US500", "NAS100", "XBRUSD"),
     "mechanism_families": ("sovereign_flow", "depletion", "portfolio_mechanics"),
     "how_to_fetch": "bancocentral.tl petroleum-fund-quarterly-reports -- PDF plus XLSX; take "
                     "capital, receipts, TRANSFERS TO STATE and the allocation, in that order"},
    {"name": "Timor-Leste Estimated Sustainable Income and the state budget transfer",
     "source": "Ministry of Finance / Jornal da Republica",
     "coverage": "2005 onward, annual", "frequency": "annual", "publication_lag_days": 0.0,
     "revisions": "re-estimated each budget", "licence": "free, public",
     "history_from": "2005", "pit_feasible": True,
     "assets": ("US500", "XBRUSD", "USDIDR"),
     "mechanism_families": ("fiscal_flow", "depletion"),
     "how_to_fetch": "jornal.gov.tl for the budget law and the authorised transfer; the ESI is "
                     "3% of petroleum wealth by statute and the EXCESS over it is the series"},
    {"name": "Timor-Leste petroleum production and the Bayu-Undan cessation",
     "source": "ANPM (Autoridade Nacional do Petroleo e Minerais)",
     "coverage": "2004 onward, monthly/annual", "frequency": "monthly",
     "publication_lag_days": 45.0, "revisions": "rare", "licence": "free, public",
     "history_from": "2004-01", "pit_feasible": True,
     "assets": ("XBRUSD", "XTIUSD", "XNGUSD"),
     "mechanism_families": ("physical_flow", "regime_break"),
     "how_to_fetch": "anpm.tl production reports; the 2023 cessation is the dated break and the "
                     "Greater Sunrise milestones are the deferred forward leg"},
    {"name": "Brunei quarterly GDP with the oil and gas sector broken out",
     "source": "DEPS, Ministry of Finance and Economy", "coverage": "2010 onward, quarterly",
     "frequency": "quarterly", "publication_lag_days": 75.0, "revisions": "revised",
     "licence": "free, public", "history_from": "2010-Q1", "pit_feasible": False,
     "assets": ("XNGUSD", "XBRUSD", "USDSGD"),
     "mechanism_families": ("release_surprise", "commodity_pass_through"),
     "how_to_fetch": "deps.mofe.gov.bn national accounts XLSX; the oil-and-gas line is most of "
                     "the level and the non-oil line is where any diversification would show"},
    {"name": "Brunei crude, condensate and LNG production and export volumes",
     "source": "Energy Department, Prime Minister's Office",
     "coverage": "2010 onward, monthly/annual", "frequency": "monthly",
     "publication_lag_days": 60.0, "revisions": "rare", "licence": "free, public",
     "history_from": "2010-01", "pit_feasible": False,
     "assets": ("XNGUSD", "XBRUSD", "JPN225"),
     "mechanism_families": ("physical_flow", "capacity"),
     "how_to_fetch": "energy.gov.bn statistics plus the Energy and Industry annual report; the "
                     "Hengyi PRODUCT export line begins 2019 and must not be spliced backwards"},
    {"name": "Japanese and Korean LNG imports by origin (the mirror statistic for Brunei)",
     "source": "Japan Customs / Korea Customs Service, via IEA and EIA compilations",
     "coverage": "2000 onward, monthly", "frequency": "monthly", "publication_lag_days": 40.0,
     "revisions": "revised once", "licence": "free, public", "history_from": "2000-01",
     "pit_feasible": True, "assets": ("XNGUSD", "JPN225", "USDKRW", "USDJPY"),
     "mechanism_families": ("mirror_statistic", "physical_flow"),
     "how_to_fetch": "the buyers' customs portals and the IEA gas trade tables; this is the "
                     "SAME TECHNIQUE the Afghan rows use -- read the partner, not the reporter"},
    {"name": "BDCB monetary and financial statistics and the currency-board backing",
     "source": "Brunei Darussalam Central Bank", "coverage": "2011 onward, monthly/quarterly",
     "frequency": "monthly", "publication_lag_days": 45.0, "revisions": "rare",
     "licence": "free, public", "history_from": "2011-01", "pit_feasible": True,
     "assets": ("USDSGD", "SGDJPY", "EURSGD"),
     "mechanism_families": ("currency_board", "liquidity"),
     "how_to_fetch": "bdcb.gov.bn/statistics monthly bulletin; the currency-in-circulation and "
                     "backing lines are the currency board's own arithmetic"},
    {"name": "RMA Bhutan rupee reserves reported separately from convertible reserves",
     "source": "Royal Monetary Authority of Bhutan", "coverage": "2005 onward, monthly",
     "frequency": "monthly", "publication_lag_days": 45.0,
     "revisions": "the split's definition has moved", "licence": "free, public",
     "history_from": "2005-07", "pit_feasible": False, "assets": ("USDINR", "XAUUSD"),
     "mechanism_families": ("reserve_stress", "par_defence"),
     "how_to_fetch": "rma.org.bt monthly statistical bulletin PDF, reserves table; the RUPEE "
                     "column is the one that binds and the 2012-13 crunch is the worked case"},
    {"name": "Druk Green Power Corporation generation and export volumes by plant",
     "source": "DGPC / Druk Holding and Investments", "coverage": "2010 onward, monthly/annual",
     "frequency": "monthly", "publication_lag_days": 60.0, "revisions": "rare",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": False,
     "assets": ("USDINR", "XALUSD", "XCUUSD"),
     "mechanism_families": ("seasonality", "physical_flow"),
     "how_to_fetch": "dgpc.bt and the DHI annual report; the WINTER IMPORT months are the same "
                     "series with the sign flipped and a summer-only sample never sees them"},
    {"name": "Bhutan trade with India by month (the mirror side, from Indian statistics)",
     "source": "NSB Bhutan and India's Department of Commerce trade statistics",
     "coverage": "2000 onward, monthly", "frequency": "monthly", "publication_lag_days": 45.0,
     "revisions": "revised", "licence": "free, public", "history_from": "2000-01",
     "pit_feasible": True, "assets": ("USDINR", "XALUSD"),
     "mechanism_families": ("mirror_statistic", "trade_flow"),
     "how_to_fetch": "nsb.gov.bt trade statistics and commerce.gov.in export-import data bank; "
                     "electricity is a line item and ferro-alloys are the other half"},
    {"name": "Da Afghanistan Bank FX auction announcements and results",
     "source": "Da Afghanistan Bank", "coverage": "2021 onward, weekly", "frequency": "weekly",
     "publication_lag_days": 0.0, "revisions": "none", "licence": "free, public",
     "history_from": "2021-09", "pit_feasible": False, "assets": ("XAUUSD", "USDINR"),
     "mechanism_families": ("auction", "monetary_flow"),
     "how_to_fetch": "dab.gov.af auction notices; availability from outside the country is "
                     "intermittent, so mirror each notice to the archive layer on the day"},
    {"name": "World Bank Afghanistan Economic Monitor (substitute national accounts)",
     "source": "World Bank", "coverage": "2021 onward, semiannual", "frequency": "semiannual",
     "publication_lag_days": 60.0, "revisions": "each edition restates",
     "licence": "free, public", "history_from": "2021-12", "pit_feasible": True,
     "assets": ("XCUUSD", "XAUUSD", "USDINR"),
     "mechanism_families": ("substitute_accounts", "regime_break"),
     "how_to_fetch": "worldbank.org Afghanistan publications; the method annex names every "
                     "underlying table, which is the source_graph layer's entry point"},
    {"name": "Mirror customs: Afghan trade as counted by Pakistan, Iran, China and Uzbekistan",
     "source": "Pakistan Bureau of Statistics / FBR, IRICA, China GACC, Uzbekistan Statistics "
               "Agency", "coverage": "2010 onward, monthly", "frequency": "monthly",
     "publication_lag_days": 35.0, "revisions": "revised by each reporter separately",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": True,
     "assets": ("XCUUSD", "XALUSD", "XTIUSD"),
     "mechanism_families": ("mirror_statistic", "trade_flow", "regime_break"),
     "how_to_fetch": "stats.customs.gov.cn monthly by-partner tables, pbs.gov.pk external trade, "
                     "IRICA and stat.uz; the post-2021 COAL export growth is visible here and "
                     "nowhere in Afghan publication at all"},
    {"name": "UNODC Afghanistan opium survey: cultivation area and farm-gate price",
     "source": "UN Office on Drugs and Crime", "coverage": "1994 onward, annual",
     "frequency": "annual", "publication_lag_days": 90.0, "revisions": "method-revised",
     "licence": "free, public", "history_from": "1994", "pit_feasible": True,
     "assets": ("XAUUSD", "USDINR"),
     "mechanism_families": ("supply_shock", "rural_income"),
     "how_to_fetch": "unodc.org crop-monitoring Afghanistan surveys; the 2022-to-2023 fall of "
                     "more than ninety-five per cent is the dated event. AN ECONOMIC OBSERVABLE "
                     "WITH NO EXECUTABLE LEG -- see NO_EXECUTABLE_LEG"},
    {"name": "UN disclosed US-dollar cash shipments to Afghanistan",
     "source": "UNAMA / OCHA", "coverage": "2021 onward, periodic", "frequency": "irregular",
     "publication_lag_days": 14.0, "revisions": "none", "licence": "free, public",
     "history_from": "2021-12", "pit_feasible": True, "assets": ("XAUUSD", "USDINR"),
     "mechanism_families": ("monetary_flow", "aid_flow"),
     "how_to_fetch": "unama.unmissions.org statements and OCHA situation reports; this is a "
                     "MATERIAL part of the country's dollar supply and it is disclosed"},
    {"name": "The four calendar tables of this pack, resolved per jurisdiction",
     "source": "this pack: national_holidays / regional_holidays / closure_breadth",
     "coverage": "2024-2026, daily", "frequency": "daily", "publication_lag_days": 0.0,
     "revisions": "PROJECTED rows move when the authority publishes",
     "licence": "derived, free", "history_from": "2024-01-01", "pit_feasible": True,
     "assets": ("USDSGD", "USDINR", "XAUUSD"),
     "mechanism_families": ("calendar_event", "holiday_liquidity"),
     "how_to_fetch": "call `regional_holidays(year)` and `closure_breadth(day)`; the Islamic and "
                     "Tibetan rows are TYPED with their authority and the Catholic and Nowruz "
                     "rows are DERIVED, so the derived half extends to any year and the typed "
                     "half stops at 2026 by design"},
    {"name": "The par-link arithmetic: USDSGD as USDBND and USDINR as USDBTN",
     "source": "this pack: par_expression()", "coverage": "continuous", "frequency": "tick",
     "publication_lag_days": 0.0, "revisions": "none", "licence": "derived, free",
     "history_from": "1967-06-12", "pit_feasible": True,
     "assets": ("USDSGD", "USDINR", "SGDJPY", "EURSGD"),
     "mechanism_families": ("par_link", "exact_expression"),
     "how_to_fetch": "no fetch: the par is a treaty and a statute, so the broker's own USDSGD "
                     "and USDINR ticks ARE the two series, with zero basis and zero lag"},
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    # ------------------------------------------------------------------ bn
    {"name": "Brunei Darussalam Central Bank as a currency board with a treaty par",
     "jurisdictions": ("bn",),
     "holds": "the issue of the Brunei dollar and the full backing behind it",
     "forced_to": ("hold the Brunei dollar interchangeable at par with the Singapore dollar",
                   "back every note issued", "publish monetary statistics"),
     "when": "continuously; the par has not moved since 12 June 1967",
     "information": ("the backing portfolio's composition", "the banking system's liquidity",
                     "currency-in-circulation before publication"),
     "constraints": ("A CURRENCY BOARD WITH A PAR REMOVES THE DECISION: there is no rate to set "
                     "and no exchange rate to defend that Singapore is not already defending",
                     "monetary conditions are the Monetary Authority of Singapore's",
                     "no lender-of-last-resort capacity of its own worth the name"),
     "instruments": ("USDSGD", "SGDJPY", "EURSGD"),
     "counterparties": ("the Monetary Authority of Singapore one link up", "the domestic banks",
                        "the Ministry of Finance and Economy"),
     "observables": ("currency in circulation and its backing", "the monthly statistics",
                     "BDCB notices and sukuk al-ijarah issuance"),
     "impact": "none directly, and saying so is the point: a BDCB notice is arithmetic on a "
               "decision taken in Singapore, which is itself anchored to the dollar",
     "persistence": "the par is fifty-eight years old and is the longest-lived object here",
     "falsifier": "an event study on BDCB notice dates shows nothing beyond what the same-day "
                  "MAS and US rate moves already carry"},
    {"name": "Brunei LNG Sdn Bhd and the Lumut liquefaction plant",
     "jurisdictions": ("bn",),
     "holds": "one of the world's oldest LNG plants and the long-term contracts that empty it",
     "forced_to": ("load contracted cargoes on schedule",
                   "reprice under oil-indexed long-term formulas rather than at a spot screen",
                   "report volumes to the Energy Department"),
     "when": "cargo by cargo; contract repricing on the formulas' own quarterly clock",
     "information": ("the loading programme before it is visible in customs data",
                     "plant availability and maintenance", "the contract formulas themselves"),
     "constraints": ("a mature field base with declining deliverability",
                     "contracts that fix the price mechanism for years at a time",
                     "two buyers' economies that dominate the offtake"),
     "instruments": ("XNGUSD", "XBRUSD", "JPN225"),
     "counterparties": ("the Japanese and Korean long-term offtakers", "Brunei Shell Petroleum",
                        "the Government of Brunei as shareholder"),
     "observables": ("the buyers' customs imports by origin", "Energy Department volumes",
                     "vessel movements out of Lumut"),
     "impact": "small in world terms and large in Brunei terms; the executable claim is about "
               "the GAS FACTOR and not about Brunei, and the pack says so",
     "persistence": "contract-length, so years",
     "falsifier": "Brunei's export volume adds nothing to a regional LNG model that already has "
                  "the buyers' total imports -- the expected result, which is why the route is "
                  "declared WEAK in NO_EXECUTABLE_LEG"},
    {"name": "Hengyi Industries at Pulau Muara Besar (the Chinese refining joint venture)",
     "jurisdictions": ("bn",),
     "holds": "the refinery that turned Brunei from a crude exporter into a product exporter",
     "forced_to": ("run to its own economics and feedstock slate",
                   "import crude it does not produce", "export products into Asian markets"),
     "when": "from the 2019 start-up; phase-two decisions on a published but slipping timetable",
     "information": ("run rates and turnaround plans", "the feedstock slate",
                     "the phase-two investment decision"),
     "constraints": ("Asian refining margins it does not set",
                     "a Chinese parent's own balance sheet and the group's credit",
                     "a single-site operation with no fallback"),
     "instruments": ("XBRUSD", "XTIUSD", "USDCNH"),
     "counterparties": ("the Brunei government as minority shareholder", "crude suppliers",
                        "Asian product buyers"),
     "observables": ("Brunei's product export line, which begins in 2019",
                     "crude import volumes into Brunei", "the parent group's disclosures"),
     "impact": "it is why Brunei's trade statistics break in 2019 and why a series spliced "
               "across that date measures a refinery rather than an economy",
     "persistence": "structural",
     "falsifier": "Brunei's product exports show no relationship to Asian refining margins once "
                  "throughput is controlled for, which would make the line accounting, not a flow"},
    {"name": "The Brunei Investment Agency as the opacity this pack measures",
     "jurisdictions": ("bn",),
     "holds": "the sovereign external wealth accumulated from six decades of hydrocarbon rent",
     "forced_to": ("invest the surplus abroad", "fund the budget gap when rent falls short"),
     "when": "continuously; nothing is disclosed on any clock",
     "information": ("its own size, allocation and return -- none of which is published",
                     "the budget's true financing position"),
     "constraints": ("no disclosure obligation at all",
                     "a state whose spending is set independently of its returns"),
     "instruments": ("USDSGD", "US500", "XAUUSD"),
     "counterparties": ("global asset managers", "the Ministry of Finance and Economy"),
     "observables": ("NOTHING DIRECT. The IMF Article IV external-asset aggregate and the "
                     "balance-of-payments financial account bound it from outside",
                     "the budget's published deficit against the published oil price"),
     "impact": "unmeasurable directly, and THE OPACITY IS THE MEASUREMENT: a NO_LAWFUL_GROUND "
               "row with a named substitute, not a gap in this pack's reading",
     "persistence": "permanent under current practice",
     "falsifier": "the Article IV external-asset aggregate tracks the published budget balance "
                  "closely enough that no undisclosed discretion is needed to explain it"},
    # ------------------------------------------------------------------ tl
    {"name": "The Timor-Leste Petroleum Fund as the whole state's balance sheet",
     "jurisdictions": ("tl",),
     "holds": "essentially all of the country's financial wealth, invested in US equities and "
              "US Treasuries under a published allocation",
     "forced_to": ("publish a QUARTERLY AUDITED report with holdings, receipts and withdrawals",
                   "transfer to the state whatever the budget law authorises",
                   "invest to a mandate it does not set"),
     "when": "quarterly, about six weeks after the quarter end",
     "information": ("the portfolio's live position", "the coming transfer request",
                     "the petroleum receipts before they are reported"),
     "constraints": ("PETROLEUM RECEIPTS HAVE ESSENTIALLY STOPPED since Bayu-Undan ceased in "
                     "2023, while the statutory withdrawal rule continues",
                     "withdrawals above the Estimated Sustainable Income need a justification "
                     "the budget law has repeatedly supplied",
                     "a return stream that is mostly US index returns"),
     "instruments": ("US500", "NAS100", "XBRUSD"),
     "counterparties": ("the state budget", "global index managers", "the external auditor"),
     "observables": ("the quarterly report's capital, receipts and TRANSFERS TO STATE lines",
                     "the ESI estimate in each budget", "the allocation"),
     "impact": "the direction runs BACKWARDS -- US index returns move the Fund, not the reverse "
               "-- and the interesting object is the WITHDRAWAL decision layered on top",
     "persistence": "the depletion path is years long and is arithmetic once the rule is fixed",
     "falsifier": "the withdrawal series is fully explained by the statutory ESI rule and the "
                  "budget cycle, leaving no discretionary component to model at all"},
    {"name": "The Government of Timor-Leste as a dollarised fiscal authority",
     "jurisdictions": ("tl",),
     "holds": "the budget, the transfer request and the Greater Sunrise decision",
     "forced_to": ("fund almost all spending from the Fund",
                   "legislate each year's transfer in the Orcamento Geral do Estado",
                   "decide on the Tasi Mane pipeline or keep deferring it"),
     "when": "annually at the budget; the pipeline decision has been deferred repeatedly",
     "information": ("the fiscal position before publication", "the Sunrise negotiations"),
     "constraints": ("NO MONETARY POLICY AT ALL: the currency is the dollar and the policy rate "
                     "is the FOMC's",
                     "a non-oil economy far too small to fund the state",
                     "a development decision whose economics depend on an oil price it cannot "
                     "forecast"),
     "instruments": ("US500", "USDIDR", "XBRUSD"),
     "counterparties": ("the Petroleum Fund", "the Sunrise joint-venture partners", "Australia",
                        "Indonesia as the dominant import source"),
     "observables": ("the budget law and the authorised transfer", "ANPM milestone filings",
                     "the Jornal da Republica"),
     "impact": "the transfer decision is the single largest dated flow in the country and it is "
               "published in Portuguese before it is reported in English anywhere",
     "persistence": "annual, with a multi-year pipeline decision on top",
     "falsifier": "budget transfers show no relationship to the oil price or the Fund's return "
                  "and are fully predicted by the prior year's spending"},
    {"name": "Banco Central de Timor-Leste as a central bank with no monetary policy",
     "jurisdictions": ("tl",),
     "holds": "the payment system, banking supervision and the OPERATIONAL MANAGEMENT of the "
              "Petroleum Fund",
     "forced_to": ("publish the Fund's quarterly audited report",
                   "operate a payment system in a currency it cannot issue",
                   "supervise a small banking sector"),
     "when": "quarterly for the Fund; monthly for the banking statistics",
     "information": ("the Fund's live valuation", "the banking system's dollar liquidity"),
     "constraints": ("IT CANNOT ISSUE ITS OWN CURRENCY and cannot be a lender of last resort in "
                     "dollars", "no interest-rate instrument", "no exchange rate to manage"),
     "instruments": ("US500", "USDIDR"),
     "counterparties": ("the Fund's external managers", "domestic banks", "the government"),
     "observables": ("the quarterly Fund report", "monetary and banking statistics",
                     "the balance of payments"),
     "impact": "as a publisher it is the most informative institution in this pack; as a "
               "monetary authority it has no impact at all, which is the honest statement",
     "persistence": "structural under dollarisation",
     "falsifier": "BCTL's banking statistics add nothing to a model that already has the Fund's "
                  "transfers and US rates"},
    {"name": "The Greater Sunrise joint venture and the deferred pipeline decision",
     "jurisdictions": ("tl",),
     "holds": "an undeveloped gas resource and a development concept the state has staked its "
              "post-Bayu-Undan future on",
     "forced_to": ("reach an investment decision or keep deferring one",
                   "agree a processing location with the state",
                   "file milestones with the regulator"),
     "when": "on a published but repeatedly deferred timetable",
     "information": ("the true project economics", "the partners' internal hurdle rates"),
     "constraints": ("a state that wants the pipeline onshore and partners who have argued "
                     "otherwise", "an oil and gas price nobody controls",
                     "a capital cost that dwarfs the country's non-oil economy"),
     "instruments": ("XBRUSD", "XNGUSD", "US500"),
     "counterparties": ("Timor GAP and the state", "the joint-venture partners", "Australia"),
     "observables": ("ANPM filings and milestone dates", "partner disclosures",
                     "the budget's treatment of the project"),
     "impact": "a dated, repeatedly deferred event whose DEFERRALS are themselves the series "
               "worth studying; the depletion path assumes it never arrives",
     "persistence": "multi-year",
     "falsifier": "deferral announcements carry no information about the Fund's withdrawal "
                  "behaviour, which would make the project irrelevant to the fiscal path"},
    # ------------------------------------------------------------------ mv
    {"name": "The Maldives Ministry of Tourism as a DAILY publisher of real activity",
     "jurisdictions": ("mv",),
     "holds": "the daily count of arrivals by nationality and by accommodation type",
     "forced_to": ("publish daily, for the previous day",
                   "split by source market and by resort versus guesthouse"),
     "when": "each day, about 11:00 Maldives time, for the day before",
     "information": ("the count before publication", "the booking pipeline via operators"),
     "constraints": ("a physical count with almost no revision scope",
                     "a single airport gateway that caps the series' upside",
                     "no published consensus to measure a surprise against"),
     "instruments": ("USDINR", "XBRUSD", "US500"),
     "counterparties": ("the resorts", "the airlines and charter operators", "the MMA"),
     "observables": ("the daily bulletin", "the monthly bed-night and occupancy tables",
                     "Velana airport movements"),
     "impact": "THE HIGHEST-FREQUENCY PUBLIC REAL-ACTIVITY SERIES IN THIS PACK, and one of the "
               "highest anywhere: a daily physical count split by source economy",
     "persistence": "daily, indefinitely",
     "falsifier": "the daily series carries nothing beyond its own seasonality and the source "
                  "markets' own risk appetite, which would make it a calendar and not a signal"},
    {"name": "The Maldives Monetary Authority defending a band from its weak edge",
     "jurisdictions": ("mv",),
     "holds": "the reserves, the rufiyaa rate and the banking system's dollar access",
     "forced_to": ("keep the rate inside the 10.28-15.42 band",
                   "publish gross reserves monthly",
                   "ration dollars to importers when usable reserves are thin"),
     "when": "monthly publication; rationing decisions continuously and unannounced",
     "information": ("usable reserves in real time", "the banks' dollar order book",
                     "the parallel premium before it is reported"),
     "constraints": ("A CURRENCY PINNED ON THE WEAK EDGE OF ITS OWN BAND has no price left to "
                     "give; the adjustment happens in the QUEUE, not the quote",
                     "reserves that have repeatedly approached crisis levels",
                     "a dated external maturity wall it must also fund"),
     "instruments": ("USDINR", "XAUUSD", "US500"),
     "counterparties": ("domestic banks and importers", "bilateral creditors",
                        "the offshore holders of the sovereign's paper"),
     "observables": ("gross and usable reserves", "the parallel premium reported in the Dhivehi "
                     "press", "the rate's distance from 15.42"),
     "impact": "the defence, not the price, is the mechanism; a devaluation would be a dated "
               "regime break and the market prices its probability in the offshore paper",
     "persistence": "the band is fourteen years old and has been tested repeatedly",
     "falsifier": "the parallel premium carries no information about the sovereign's offshore "
                  "spread once global risk and the oil price are controlled for"},
    {"name": "The Maldivian resort industry as the economy's single production function",
     "jurisdictions": ("mv",),
     "holds": "the bed capacity, the dollar revenue and most of the country's formal employment",
     "forced_to": ("price in dollars and surrender some of it domestically",
                   "operate a fixed bed inventory that changes only with construction",
                   "absorb the arrivals cycle with no ability to store the product"),
     "when": "continuously, with a pronounced European winter and Asian holiday seasonality",
     "information": ("forward bookings", "rate realisation before it is surveyed"),
     "constraints": ("an unstorable product and a fixed inventory",
                     "imported everything: food, fuel, staff and construction materials",
                     "a jet-fuel and airfare cost it does not control"),
     "instruments": ("XBRUSD", "US500", "USDINR"),
     "counterparties": ("international tour operators and airlines", "the banks",
                        "the government as licensor and taxer"),
     "observables": ("bed-nights, occupancy and average stay", "capacity announcements",
                     "the daily arrivals split"),
     "impact": "directly about a quarter of GDP and indirectly around seventy per cent; there "
               "is no second sector to average against",
     "persistence": "structural; capacity changes over years",
     "falsifier": "occupancy shows no relationship to the oil price through airfare once global "
                  "demand is controlled for, breaking the pack's travel-cost channel"},
    {"name": "The Maldivian sovereign as a dated maturity wall",
     "jurisdictions": ("mv",),
     "holds": "the external debt stock, the guarantees and the 2026 sukuk",
     "forced_to": ("service dated maturities in dollars from a reserve it also uses to defend a "
                   "peg", "publish a quarterly debt bulletin",
                   "seek bilateral support when the wall approaches"),
     "when": "on the maturity schedule's own dates, which are public years in advance",
     "information": ("the bilateral negotiations in progress", "the true usable reserve"),
     "constraints": ("ONE POOL OF DOLLARS SERVING TWO CLAIMS: the peg's defence and the debt "
                     "service", "a tourism receipt stream that is seasonal and weather-exposed",
                     "an offshore price for its own paper that moves faster than its bulletin"),
     "instruments": ("USDINR", "XAUUSD", "US500"),
     "counterparties": ("bondholders", "bilateral creditors", "the MMA"),
     "observables": ("the quarterly maturity profile", "the offshore price of the sukuk",
                     "reserve coverage of the next twelve months"),
     "impact": "the clearest dated stress point in the pack and the one an event study can "
               "actually align on",
     "persistence": "until the wall is passed or restructured",
     "falsifier": "the approach of a dated maturity produces no measurable change in the "
                  "parallel premium or in reserve behaviour"},
    # ------------------------------------------------------------------ bt
    {"name": "Druk Green Power Corporation as a monsoon-driven exporter",
     "jurisdictions": ("bt",),
     "holds": "the hydropower plants and the export contracts with Indian buyers",
     "forced_to": ("generate what the rivers give it, when they give it",
                   "export the summer surplus into India at contracted tariffs",
                   "IMPORT power in winter when flows fall"),
     "when": "the monsoon's own calendar: high flow June to September, low flow December to "
             "February, every single year",
     "information": ("reservoir and flow conditions before they are reported",
                     "outage and commissioning schedules"),
     "constraints": ("RUN-OF-RIVER PLANTS WITH LITTLE STORAGE, so generation follows rainfall "
                     "rather than demand", "tariffs fixed by bilateral agreement",
                     "a single buyer country"),
     "instruments": ("USDINR", "XALUSD", "XCUUSD"),
     "counterparties": ("the Indian buyers and the central grid", "Druk Holding and Investments",
                        "the Government of India as financier of several plants"),
     "observables": ("monthly generation and export volumes by plant",
                     "the winter IMPORT line", "Indian grid data"),
     "impact": "it is most of Bhutan's exports and most of its government revenue; on India's "
               "grid it is small, which is why NO_EXECUTABLE_LEG calls this route WEAK",
     "persistence": "annual and utterly repeating",
     "falsifier": "the seasonal export reversal carries nothing about USDINR or about Bhutan's "
                  "own rupee reserve once Indian monsoon rainfall is controlled for"},
    {"name": "The Royal Monetary Authority defending a par it cannot devalue",
     "jurisdictions": ("bt",),
     "holds": "the 1:1 ngultrum parity and the RUPEE reserve that actually funds imports",
     "forced_to": ("hold the parity", "publish rupee reserves separately from convertible ones",
                   "ration or borrow rupees when the rupee reserve runs thin"),
     "when": "monthly publication; rationing episodically and on dated occasions",
     "information": ("the rupee position in real time", "the credit growth funding imports"),
     "constraints": ("A PAR THAT IS POLITICALLY AND PRACTICALLY UNBREAKABLE: the rupee "
                     "circulates domestically, so a devaluation would devalue money already in "
                     "Bhutanese pockets",
                     "an open border that makes capital controls partly notional",
                     "import demand driven by hydropower construction it also wants"),
     "instruments": ("USDINR", "XAUUSD"),
     "counterparties": ("the Reserve Bank of India", "domestic banks", "the government"),
     "observables": ("the rupee/convertible reserve split", "credit growth",
                     "the 2012-13 crunch as the worked historical case"),
     "impact": "the parity never moves, so the adjustment appears as a RUPEE SHORTAGE inside an "
               "otherwise adequate reserve -- an object with no price and a real economic cost",
     "persistence": "fifty-one years and counting",
     "falsifier": "rupee-reserve stress episodes produce no measurable change in Bhutanese "
                  "import volumes or in the credit series, making the constraint notional"},
    {"name": "Druk Holding and Investments as the state's entire corporate sector",
     "jurisdictions": ("bt",),
     "holds": "the state's commercial holdings including the power companies",
     "forced_to": ("publish an annual report", "dividend to the state budget",
                   "finance hydropower construction that is mostly Indian-funded"),
     "when": "annually, with project milestones in between",
     "information": ("project cost overruns before they are disclosed",
                     "the dividend capacity for the coming year"),
     "constraints": ("projects whose delays have run to years",
                     "a debt stock denominated in rupees against revenue also in rupees",
                     "a single counterpart country for both financing and offtake"),
     "instruments": ("USDINR", "XALUSD"),
     "counterparties": ("the state budget", "Indian financiers and contractors",
                        "the RMA"),
     "observables": ("the annual report", "project commissioning dates",
                     "the dividend to the budget"),
     "impact": "the commissioning of a large plant is a dated step change in export capacity and "
               "is one of the few genuinely forecastable events in this pack",
     "persistence": "project-length, so years",
     "falsifier": "commissioning dates produce no step in the export series, which would mean "
                  "the capacity was already being counted somewhere else"},
    {"name": "The Bhutanese household and importer facing a border that never closes",
     "jurisdictions": ("bt",),
     "holds": "rupee-denominated purchasing power and an import basket that is mostly Indian",
     "forced_to": ("buy in rupees", "hold savings in a currency pegged to a currency it does "
                   "not control", "absorb Indian inflation directly"),
     "when": "continuously",
     "information": ("local price conditions ahead of the CPI"),
     "constraints": ("IMPORTED INFLATION BY CONSTRUCTION: the peg means India's price level is "
                     "Bhutan's", "capital controls that an open border makes partly notional",
                     "no domestic savings instrument beyond bank deposits"),
     "instruments": ("USDINR", "XAUUSD"),
     "counterparties": ("Indian suppliers", "the domestic banks"),
     "observables": ("Bhutanese CPI against Indian CPI", "credit growth",
                     "cross-border rupee flows"),
     "impact": "the household channel is why the rupee reserve is a real constraint rather than "
               "an accounting one",
     "persistence": "structural",
     "falsifier": "Bhutanese CPI diverges persistently from Indian CPI, which would mean the "
                  "border and the peg are less binding than the pack claims"},
    # ------------------------------------------------------------------ af
    {"name": "Da Afghanistan Bank managing a flow with a frozen stock",
     "jurisdictions": ("af",),
     "holds": "the afghani's issue and the published FX auctions; NOT its reserves, which are "
              "frozen abroad",
     "forced_to": ("auction dollars it must first obtain", "publish the auction results",
                   "operate without normal correspondent banking"),
     "when": "weekly auctions; results published on the day",
     "information": ("the cash position before the auction", "the banks' dollar demand"),
     "constraints": ("RESERVES FROZEN ABROAD SINCE AUGUST 2021, with part transferred to a "
                     "Swiss-based fund in 2022",
                     "severed correspondent relationships",
                     "a cash economy in which the UN's disclosed dollar shipments are material"),
     "instruments": ("XAUUSD", "USDINR"),
     "counterparties": ("licensed money-changers and banks", "the UN agencies bringing cash",
                        "the de facto fiscal authority"),
     "observables": ("auction size, allotment and cut-off", "the reference rate",
                     "the Sarai Shahzada quotes reported in the press"),
     "impact": "the one regularly published monetary number the jurisdiction still produces; the "
               "desk reads it and transacts in nothing",
     "persistence": "as long as the current arrangement holds",
     "falsifier": "auction outcomes carry no information about the money-changer rate, which "
                  "would mean the official channel is not the marginal one"},
    {"name": "The Afghan coal and mineral exporter counted only by its neighbours",
     "jurisdictions": ("af",),
     "holds": "coal, talc, chromite and marble moving across Torkham, Chaman, Hairatan and "
              "Islam Qala",
     "forced_to": ("cross a border that counts what Afghanistan does not",
                   "accept the buyer country's price and duty regime",
                   "route payment through hawala rather than banks"),
     "when": "continuously, with sharp seasonal and policy-driven swings",
     "information": ("the truck queue at the crossings in real time",
                     "duty and closure decisions before they are announced"),
     "constraints": ("BORDER CLOSURES DECIDED BY THE OTHER SIDE, repeatedly and at short notice",
                     "no domestic customs publication to verify against",
                     "buyers whose own tariffs move the flow"),
     "instruments": ("XCUUSD", "XALUSD", "XTIUSD"),
     "counterparties": ("Pakistani, Iranian, Chinese and Uzbek importers",
                        "the de facto revenue authority"),
     "observables": ("MIRROR CUSTOMS from all four partners",
                     "crossing closure announcements", "trader reports at low weight"),
     "impact": "coal exports grew sharply after 2021 and that growth is visible ONLY in the "
               "partners' tables, which is this pack's clearest worked substitution",
     "persistence": "structural, punctuated by closures",
     "falsifier": "the four partners' mirror tables disagree with each other by more than their "
                  "own revision histories, which would make the substitute unusable"},
    {"name": "The Mes Aynak concession and the undeveloped copper and lithium resource",
     "jurisdictions": ("af",),
     "holds": "one of the world's larger undeveloped copper deposits and, separately, very large "
              "undeveloped lithium resources",
     "forced_to": ("negotiate with a de facto authority most states do not recognise",
                   "build infrastructure that does not exist",
                   "clear an archaeological site of international significance"),
     "when": "on a concession history running since 2008 with renewed activity announced since "
             "2024",
     "information": ("the true development timetable", "the investors' internal economics"),
     "constraints": ("SEVENTEEN YEARS WITHOUT PRODUCTION",
                     "no rail, no power and no port access",
                     "international measures that constrain the financing"),
     "instruments": ("XCUUSD", "XALUSD", "USDCNH"),
     "counterparties": ("the Chinese concession holders", "the de facto mining authority"),
     "observables": ("announcement dates and their repeated slippage",
                     "the World Bank Monitor's mining section", "Chinese partner disclosures"),
     "impact": "ZERO ON TODAY'S COPPER BALANCE and non-zero as an option; the pack carries it as "
               "a dated announcement series whose SLIPPAGE is the measurable part",
     "persistence": "decades",
     "falsifier": "announcement dates produce no measurable response in the copper complex, "
                  "which is the expected result and is worth recording as such"},
    {"name": "The Afghan rural household after the 2022 opium ban",
     "jurisdictions": ("af",),
     "holds": "the land and the labour that produced most of the world's illicit opiates until "
              "the April 2022 ban",
     "forced_to": ("switch to wheat and other low-value crops",
                   "absorb a collapse in cash income measured by UNODC at more than ninety-five "
                   "per cent of cultivation area",
                   "meet food needs from a market whose prices it does not set"),
     "when": "from the April 2022 ban; measured in the 2023 survey and after",
     "information": ("planting intentions before the survey sees them"),
     "constraints": ("no credit system to smooth the transition",
                     "a wheat price set regionally", "drought and water availability"),
     "instruments": ("XAUUSD", "USDINR"),
     "counterparties": ("regional traders", "the humanitarian agencies", "the de facto authority"),
     "observables": ("UNODC cultivation area and farm-gate price",
                     "WFP food-security assessments", "regional wheat prices"),
     "impact": "AN ECONOMIC OBSERVABLE WITH NO EXECUTABLE LEG. The desk will never trade this "
               "commodity; what is testable is a large, dated, quantified RURAL INCOME shock "
               "whose only lawful executable expression is the regional gold and trade channel, "
               "and the honest prior is that the effect is small and slow",
     "persistence": "years; a cultivation collapse takes years to reverse",
     "falsifier": "no measurable regional income or gold-demand response around the dated survey "
                  "publications, which is the expected result and is recorded as one"},
    # ------------------------------------------------------------------ cross-cutting
    {"name": "The mirror-statistics reader as this pack's own method",
     "jurisdictions": ("af", "bn", "bt"),
     "holds": "the technique that makes three of these five readable at all: read the PARTNER's "
              "published customs table rather than the subject's own",
     "forced_to": ("accept the partner's classification, timing and revisions",
                   "reconcile four partners who disagree",
                   "declare the residual rather than smoothing it"),
     "when": "monthly, on each partner's own publication clock",
     "information": ("nothing privileged; every input is a published national statistic"),
     "constraints": ("valuation and timing differences between reporters",
                     "transit trade double-counted or missed",
                     "a partner's own political incentives in what it reports"),
     "instruments": ("XCUUSD", "XALUSD", "XNGUSD", "JPN225"),
     "counterparties": ("the four Afghan partners", "Japan and Korea for Brunei's cargoes",
                        "India for Bhutan's power"),
     "observables": ("the four mirror tables and their disagreement",
                     "the buyers' LNG imports by origin", "Indian grid imports from Bhutan"),
     "impact": "it is the difference between three unreadable jurisdictions and three readable "
               "ones, and it is the same technique the `caucasus_central_asia` pack uses",
     "persistence": "as long as the partners publish",
     "falsifier": "mirror totals diverge from the subject's own figures, where those exist, by "
                  "more than the partners' revision histories can explain"},
    {"name": "The single-factor property itself, as a cross-sectional hypothesis",
     "jurisdictions": ("bn", "tl", "mv", "bt", "af"),
     "holds": "the claim that unites this pack: each economy has ONE published dominant exposure "
              "and no hedge against it",
     "forced_to": ("be tested rather than asserted",
                   "survive the observation that the five share no geography, no currency bloc "
                   "and no trade agreement"),
     "when": "on each jurisdiction's own publication clock, which is why MAR-L is quarterly",
     "information": ("nothing; this actor is the pack's own hypothesis wearing a row"),
     "constraints": ("FIVE JURISDICTIONS IS A TINY CROSS-SECTION and the pack says so",
                     "the five factors are genuinely unrelated, so a common response would "
                     "itself be evidence of a global factor rather than of this property",
                     "no common calendar, no common currency, no common counterparty"),
     "instruments": ("USDSGD", "USDINR", "XBRUSD"),
     "counterparties": ("the gauntlet", "the sibling packs that own the other ends"),
     "observables": ("the five factor series", "their cross-correlation, which should be low",
                     "their individual response to global risk"),
     "impact": "if the property has content, a single-factor economy's dominant series should "
               "explain more of its own macro than a diversified economy's does -- THE HONEST "
               "PRIOR IS THAT THIS HAS VERY LITTLE EXECUTABLE CONTENT and MAR-L exists to "
               "measure that rather than to assume it",
     "persistence": "structural",
     "falsifier": "the five dominant series show no more explanatory power over their own "
                  "economies than a diversified comparator's does, which would retire the "
                  "pack's organising claim while leaving all five mechanisms intact"},
)

# ---8<--- APPEND HERE
