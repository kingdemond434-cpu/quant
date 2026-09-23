"""THE FOUR SMALLER GULF STATES -- Qatar, Kuwait, Oman and Bahrain -- as FOUR DIFFERENT MACHINES.

WHY ONE PACK AND NOT FOUR, AND WHY NOT A FOOTNOTE TO SAUDI ARABIA OR THE UAE. The desk already
holds `sa` (the marginal barrel, the weekly point-of-sale print, the FOMC-imported policy date)
and `ae` (the region's dollar funding, Jebel Ali throughput, the 2022-01-03 working-week move).
This pack is their COMPLEMENT, and it exists because the four states it answers for are NOT
scaled-down copies of either. Each one carries a mechanism the other six Gulf packs cannot:

  1. QATAR IS A PUBLISHED MULTI-YEAR SUPPLY CURVE FOR GAS. The North Field expansion -- 77 mtpa
     today, 110 mtpa (North Field East), 126 mtpa (North Field South) and 142 mtpa (North Field
     West) on DATED, STATE-ANNOUNCED trains -- is the single largest scheduled addition to world
     LNG supply, and it is a CALENDAR rather than a forecast. A supply curve with dates on it is
     exactly the object a desk can test: `north_field_capacity(year)` returns the announced
     nameplate for a year, and every XNGUSD claim in this pack is conditioned on it.
  2. QATAR'S CONTRACTS ARE CHANGING PRICE FORMULA IN PUBLIC. QatarEnergy's long-term SPAs ran on
     Brent slopes (roughly 10-13% of Brent) for two decades; the 2022-2024 European and Chinese
     deals are 27-year agreements struck as the seller moves toward hub-indexed and
     destination-flexible terms. That is a SLOW, DATED CHANGE IN THE TRANSMISSION FUNCTION
     between XBRUSD and XNGUSD, which is a regime variable rather than a signal.
  3. THE QATARI RIYAL HAS A NAMED ERA IN WHICH THE PEG BROKE OFFSHORE. From 2017-06-05 to the
     Al-Ula declaration of 2021-01-05 the blockade cut Qatar's correspondent-banking lines; the
     ONSHORE QCB rate never left 3.64 while the OFFSHORE riyal traded far weaker and the forward
     points blew out. Any pooled study of "the Gulf pegs" across those years is measuring two
     different instruments with one name, which is why GULF-C is a domain and not a sentence.
  4. KUWAIT IS THE ONLY GULF CURRENCY THAT IS NOT A DOLLAR PEG. The dinar is fixed to an
     UNDISCLOSED weighted basket and the Central Bank of Kuwait sets the rate itself each
     business day. The weights are a state secret, which makes the USD beta an ESTIMATION
     PROBLEM with a published daily answer sheet -- `kwd_basket_beta` does exactly that
     regression -- and it makes Kuwait the only Gulf state where an FX move is information
     rather than arithmetic.
  5. KUWAIT'S FISCAL PLUMBING IS A LAW AND A PARLIAMENT. Ten per cent of state revenue goes to
     the Future Generations Fund by statute; the FGF is legally unreachable for spending; the
     General Reserve Fund is what actually pays salaries; and the debt law has been blocked in
     the National Assembly for years, so a deficit is financed by SELLING ASSETS rather than by
     issuing. That is a forced seller with a legal timetable, which is the rarest actor shape
     this desk collects.
  6. OMAN IS IN OPEC+ AND NOT IN OPEC. It joined the Declaration of Cooperation in 2016 and has
     never been an OPEC member, so its quota arrives through the DoC and its compliance is
     reported separately. Its crude is the ASIAN SOUR BENCHMARK: the DME (now Gulf Mercantile
     Exchange) Oman contract settles in a Singapore-afternoon window and is the price Asian
     refiners' margins are struck against.
  7. OMAN IS THE ONLY GULF EXPORTER OUTSIDE THE STRAIT OF HORMUZ. Duqm, Ras Markaz and Sohar
     load on the Arabian Sea. Every other Gulf barrel and every Qatari cargo must transit
     Hormuz. That makes Oman the chokepoint's NATURAL CONTROL -- an event that moves Gulf crude
     through the strait and does NOT move Omani loadings is a chokepoint event; one that moves
     both is a price event. No other pack on this desk owns a control of that shape.
  8. BAHRAIN IS A PEG WITH AN EXTERNAL GUARANTEE. The dinar is fixed at 0.376 to the dollar on
     the smallest reserves and the weakest fiscal position in the GCC, and it is held there by
     GCC support -- the USD 10bn package agreed in October 2018 being the dated case. So Bahrain
     prices Gulf political cohesion rather than Bahraini fundamentals, and BHIBOR is the
     region's cheapest public stress gauge.

WHAT IS EXECUTABLE AND WHAT IS NOT. QAR, KWD, OMR and BHD are ALL ABSENT from
`data/universe/universe.json`, as are the four exchanges' indices, the DME Oman futures curve,
the GCC sovereign USD bonds and every interbank fixing named here. Each is in
`TRANSMISSION_TARGETS` with its peg parameters and the broker symbols its economics reach, so an
absent instrument mints a transmission hypothesis and never a cell that can never be filled
(L1.49). Gas, crude, gold, the dollar legs, the Asian buyers' currencies, the two Treasury
tenors, the two index legs and the food imports are what the box can actually put an order into.

THE TWO-LANE ORDER (2026-09-06) IS LOUD HERE. QatarEnergy, KPC, OQ, Bapco, Nakilat, Ooredoo,
Industries Qatar, Zain, Alba, NBK, QNB and Ahli United are the names this ground talks about and
every one of them is an EVENT-lane instrument. They appear in this file as ACTORS and as
TERMINOLOGY so an Arabic-language miner recognises the words. Not one is a symbol in any
instrument tuple.

NO CRYPTO-EXCHANGE GROUND IS HUNTED (mandate 2026-08-18), and that refusal is worth repeating in
a Gulf pack: Bahrain licenses crypto venues and the temptation is local. Broker crypto CFDs stay
inside the MT5 universe; no venue, order book or exchange feed is named as a source anywhere
below.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime
from itertools import pairwise
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "GULF"
NAME = "Gulf states (Qatar, Kuwait, Oman, Bahrain)"
REGION_COMMAND = "mea"             # the framework's command; the forest is mena
REGION_DESK = "MENA"
FOREST = "mena"
CURRENCY = "QAR"                   # the pack's nominal currency; the other three are below
#: THE FOUR ISO-2 CODES THIS PACK ANSWERS FOR. `check_regional_parity.jurisdictions_of` reads
#: this tuple and nothing else: a multi-country pack that declares nothing is credited with ONE
#: country, which would leave three of the parity fence's twenty-six unanswered while the work
#: sat on disk.
JURISDICTIONS: tuple[str, ...] = ("qa", "kw", "om", "bh")

#: THE FOUR CURRENCIES AND THEIR PEG FACTS. Three are dollar pegs with published parities; one is
#: not a dollar peg at all. `mid` is the declared central parity, `band` the declared or observed
#: intervention bounds, and `since` the date the current arrangement took effect. NONE of the
#: four is quoted by this broker -- see TRANSMISSION_TARGETS.
CURRENCIES: dict[str, dict[str, Any]] = {
    "QAR": {"jurisdiction": "qa", "name": "Qatari riyal", "regime": "usd_peg",
            "mid": 3.6400, "band": (3.6385, 3.6415), "since": "1980-03-19",
            "authority": "Qatar Central Bank (مصرف قطر المركزي)",
            "fact": "QCB buys dollars from banks at 3.6385 and sells at 3.6415, so the onshore "
                    "riyal is a 30-pip corridor and not a free price; the 2017-2021 blockade "
                    "detached the OFFSHORE riyal from it while the onshore rate never moved"},
    "KWD": {"jurisdiction": "kw", "name": "Kuwaiti dinar", "regime": "undisclosed_basket",
            "mid": 0.3070, "band": (), "since": "2007-05-20",
            "authority": "Central Bank of Kuwait (بنك الكويت المركزي)",
            "fact": "THE ONLY GULF CURRENCY THAT IS NOT PEGGED TO THE DOLLAR. The CBK announces "
                    "a customer rate every business day against an undisclosed weighted basket "
                    "of the currencies of Kuwait's main trade and financial partners. The "
                    "weights have never been published, so the USD beta is ESTIMATED from the "
                    "published fixings -- see `kwd_basket_beta` -- and never assumed to be one"},
    "OMR": {"jurisdiction": "om", "name": "Omani rial", "regime": "usd_peg",
            "mid": 0.384500, "band": (0.384400, 0.385000), "since": "1986-01-01",
            "authority": "Central Bank of Oman (البنك المركزي العماني)",
            "fact": "the CBO buys dollars from licensed banks at 0.3845 and sells at 0.3850; the "
                    "rial is the second most valuable currency in the world by parity and has "
                    "not been revalued since 1986, through two fiscal crises and a rating cut "
                    "to sub-investment grade in 2020 that was reversed by 2023-2024"},
    "BHD": {"jurisdiction": "bh", "name": "Bahraini dinar", "regime": "usd_peg_with_guarantee",
            "mid": 0.3760, "band": (0.3760, 0.3770), "since": "2001-12-01",
            "authority": "Central Bank of Bahrain (مصرف البحرين المركزي)",
            "fact": "THE ONLY ASYMMETRIC CORRIDOR OF THE FOUR: the declared parity 0.3760 sits "
                    "at the STRONG EDGE of the CBB's own dealing range (it sells dollars to "
                    "banks at 0.3760 and buys them at 0.3770), so the dinar can only ever be "
                    "quoted weaker than par and `peg_band_state` reports par as AT_STRONG_EDGE "
                    "by construction. The peg's real backing is GCC SUPPORT rather than "
                    "Bahraini reserves -- the USD 10bn package agreed in October 2018 is the "
                    "dated case -- so BHD forwards price Gulf political cohesion"},
}

FISCAL_YEAR_END = "12-31"          # Qatar, Oman and Bahrain run the calendar year
#: KUWAIT IS THE EXCEPTION AND IT MATTERS: the Kuwaiti fiscal year runs 1 April to 31 March, so
#: the budget, the 10%-of-revenue Future Generations Fund transfer and the General Reserve Fund
#: liquidity squeeze all land on a DIFFERENT quarter boundary from its neighbours'. A pooled
#: "Gulf fiscal year end" study is measuring two calendars.
FISCAL_YEAR_ENDS: dict[str, str] = {"qa": "12-31", "kw": "03-31", "om": "12-31", "bh": "12-31"}

NATIVE_LANGUAGES: tuple[str, ...] = ("ar", "en")
COT_CURRENCY = ""                  # no CFTC contract exists for QAR, KWD, OMR or BHD
EXPORT_ECONOMY = "energy_exporter"
RETAIL_LEVERAGE_REGIME = "restricted"
#: Per jurisdiction, because the four are not one regime: Bahrain's CBB licenses investment
#: firms that may offer leveraged FX to residents, while Qatar, Kuwait and Oman license no
#: retail margin brokerage at all and their residents reach the market through offshore accounts.
RETAIL_LEVERAGE_BY_JURISDICTION: dict[str, str] = {
    "qa": "restricted", "kw": "restricted", "om": "restricted", "bh": "capped"}

MISSION = ("mine the four smaller Gulf states as four different machines: Qatar's dated North "
           "Field capacity schedule and its SPA pricing shift, Kuwait's undisclosed basket and "
           "its asset-selling fiscal law, Oman's non-OPEC OPEC+ quota and its Hormuz-bypass "
           "loadings under the DME Oman marker, Bahrain's externally guaranteed peg and BHIBOR "
           "as the region's stress gauge -- plus the shared GCC peg cluster, the strait, the "
           "Hijri demand season and the dated index-inclusion rebalances")

#: The instruments this pack may compile a cell against. Every one is in the broker registry and
#: none is a single-name equity. All four local currencies are absent (see TRANSMISSION_TARGETS).
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "XNGUSD",                                          # the North Field schedule's own price
    "XBRUSD", "XTIUSD",                                # the OSP slope, the DoC quota, the strait
    "XAUUSD", "XAGUSD",                                # reserves, the Eid retail season, haven
    "USDX", "EURUSD", "USDCHF", "USDJPY",              # the peg's anchor and the haven legs
    "USDINR", "USDCNH", "USDKRW", "USDSGD",            # the Asian buyers and the remittance leg
    "USDTRY", "USDILS", "USDZAR",                      # the regional-risk and EM-stress beta
    "US500", "UK100", "JPN225",                        # the risk leg and the Asian refiner leg
    "UST05Y", "UST10Y",                                # what a dollar peg actually imports
    "WHEAT", "CORN", "SUGAR",                          # the Ramadan/Hajj food import
)

#: EVERY LOCAL PRICE THIS PACK IS ABOUT, NAMED ABSENT WITH WHAT CARRIES IT. `proxies` must all
#: resolve in the broker registry -- a transmission target with an unquotable carrier is an
#: absence dressed as a route.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "QAR (the Qatari riyal, onshore QCB corridor 3.6385/3.6415)",
     "venue": "Qatar Central Bank and the domestic interbank market",
     "why": "the onshore riyal cannot move; the INFORMATION is in the forward points and in the "
            "offshore rate, and the executable legs are the dollar and the gas the peg is "
            "financed by",
     "peg": "3.6400 to USD since 1980-03-19; corridor 3.6385-3.6415",
     "proxies": ("USDX", "XNGUSD", "UST10Y")},
    {"name": "The OFFSHORE riyal and the QAR forward points (the blockade instrument)",
     "venue": "the offshore forward and non-deliverable market",
     "why": "between 2017-06-05 and 2021-01-05 the offshore riyal traded materially weaker than "
            "3.64 while the onshore rate never moved; the forward-points series is the only "
            "public read on Gulf political stress with a price attached",
     "peg": "detached from the onshore corridor for the blockade era only",
     "proxies": ("USDX", "USDTRY", "XAUUSD")},
    {"name": "KWD (the Kuwaiti dinar, undisclosed weighted basket)",
     "venue": "Central Bank of Kuwait daily customer rate",
     "why": "the only Gulf currency whose fixing carries information; its USD beta is estimable "
            "from the published daily rates against the majors and is not one",
     "peg": "undisclosed basket since 2007-05-20; no published band",
     "proxies": ("USDX", "EURUSD", "USDJPY")},
    {"name": "OMR (the Omani rial, 0.3845/0.3850 CBO corridor)",
     "venue": "Central Bank of Oman",
     "why": "a hard dollar peg on a small reserve base; the stress shows in the OMR forward "
            "points and the sovereign spread rather than in the spot rate",
     "peg": "0.384500 to USD since 1986; corridor 0.384400-0.385000",
     "proxies": ("USDX", "XBRUSD", "UST05Y")},
    {"name": "BHD (the Bahraini dinar, 0.376 with a GCC guarantee)",
     "venue": "Central Bank of Bahrain",
     "why": "the weakest peg in the GCC and therefore the one that prices the GUARANTEE; the "
            "dinar forward is a Gulf-cohesion instrument and is unquotable here",
     "peg": "0.376 to USD since 2001-12-01",
     "proxies": ("USDX", "XBRUSD", "USDTRY")},
    {"name": "BHIBOR, KIBOR (Kuwait), QIBOR and the Omani interbank rate",
     "venue": "the four central banks' published interbank fixings",
     "why": "three of the four import the Fed's rate mechanically, so the SPREAD to SOFR is the "
            "only local information in a Gulf money-market rate; Bahrain's spread is the "
            "region's cheapest public stress gauge",
     "peg": "n/a (rates, not parities)",
     "proxies": ("UST05Y", "UST10Y", "USDX")},
    {"name": "The DME / Gulf Mercantile Exchange Oman Crude Oil Futures contract (OQD)",
     "venue": "Dubai Mercantile Exchange, settled in a Singapore-afternoon window",
     "why": "the Asian sour benchmark and the price Oman's and Dubai's OSPs are struck against; "
            "no CFD is quoted, so the Brent-Dubai exchange-for-swaps economics route into the "
            "two crude legs and into the Asian refiner indices",
     "peg": "n/a (a futures marker)",
     "proxies": ("XBRUSD", "XTIUSD", "JPN225")},
    {"name": "QE Index (Qatar), Boursa Kuwait All Share / Premier, MSX30 (Oman), "
             "Bahrain All Share",
     "venue": "the four national exchanges",
     "why": "no CFD is quoted on any of them; the MSCI and FTSE upgrades that rebalance them are "
            "DATED events whose flow arrives through global EM funds, so the executable leg is "
            "the risk complex and the dollar",
     "peg": "n/a (equity indices)",
     "proxies": ("US500", "UK100", "USDX")},
    {"name": "Qatari, Omani and Bahraini USD sovereign bonds and their CDS",
     "venue": "the international bond market",
     "why": "the spread is where a Gulf fiscal shock actually prints; no Gulf credit instrument "
            "is quoted here, so the duration leg is the Treasury curve and the credit leg is "
            "declared UNMEASURED by name rather than proxied silently",
     "peg": "n/a (credit)",
     "proxies": ("UST05Y", "UST10Y", "USDTRY")},
    {"name": "QatarEnergy long-term SPA slopes and the LNG term price",
     "venue": "bilateral contracts; the slope is disclosed only in fragments",
     "why": "the transmission function between XBRUSD and XNGUSD for term Asian and European "
            "cargoes; the slope is the regime variable GULF-B conditions on and it is not a "
            "published series",
     "peg": "n/a (a contract formula)",
     "proxies": ("XNGUSD", "XBRUSD", "USDJPY")},
)

# --------------------------------------------------------------------------- the central banks
#: The pack-level central bank is the QCB, because QAR is the pack's declared currency. The other
#: three are carried in CENTRAL_BANKS at full depth: a Gulf pack that describes one monetary
#: authority and calls it "the Gulf" has erased the only Gulf currency that is not a dollar peg.
CENTRAL_BANK: dict[str, Any] = {
    "name": "Qatar Central Bank -- مصرف قطر المركزي",
    "short": "QCB",
    "framework": "peg",
    "committee": "the Governor and the Board of Directors; there is no published voting "
                 "committee and no minutes, because there is no independent rate decision to "
                 "minute",
    "policy_instrument": "the QCB deposit rate (QCBDR), the lending rate (QCBLR) and the repo "
                         "rate, moved to track the Federal Reserve",
    "mandate": "maintain the riyal's parity at 3.64 to the dollar and the stability of the "
               "banking system; there is NO inflation target and no domestic rate cycle, so a "
               "'Qatari rate surprise' is a category error unless the QCB DEVIATES from the Fed "
               "-- and a deviation is a peg-stress observable rather than a policy one",
    "decision_rule": "the QCB announces within hours of an FOMC decision, usually the same "
                     "evening Doha time; the Qatari policy date list IS the FOMC date list",
    "decision_calendar_rule": "no calendar of its own: read the FOMC calendar and check "
                              "qcb.gov.qa for the same-day circular; the SIZE of the move is the "
                              "only degree of freedom and it has been used (in 2022-2023 the "
                              "Gulf central banks did not always match the Fed step for step)",
    "decision_dates": (),
    "dates_status": "DECLARED EMPTY ON PURPOSE. The QCB has no scheduled decision dates; "
                    "inventing a list here would manufacture events. The event clock is the "
                    "FOMC's, and the Gulf-specific object is the SPREAD between the Fed's step "
                    "and the QCB's, which is read from the circulars",
    "decision_time_utc": "19:30",
    "announce_local": "the same evening Asia/Qatar (UTC+3 all year, NO daylight saving anywhere "
                      "in the Gulf -- the one clock fact that makes a Gulf session study stable "
                      "where a European one is not)",
    "dst_rule": "none; Qatar, Kuwait and Bahrain keep UTC+3 and Oman UTC+4 all year",
    "minutes_lag_days": 0,
    "publication_classes": ("qcb_circular", "monetary_bulletin", "financial_stability_review",
                            "annual_report", "treasury_bill_auction", "monetary_statistics"),
    "policy_rate_series": "QCB:deposit_rate",
    "expected_rate_series": "FOMC:target_range",
    "consensus_proxy": "the FOMC's own expected path; the local proxy is the QIBOR fixing and "
                       "the Treasury-bill cut-off between FOMC dates",
    "consensus_proxy_trap": "QIBOR is administered and thin, so it moves with BANK LIQUIDITY and "
                            "with the state's deposit placements rather than with expectations; "
                            "a QIBOR move is a funding fact first and a rate view second",
    "reserves_clock": "international reserves and foreign currency liquidity monthly in the QCB "
                      "monetary bulletin; the QIA's holdings are NOT in it and are not published",
    "programme": "none; Qatar has no IMF programme and no need of one",
    "off_cycle": ("2017-06 the blockade: the state placed deposits into the domestic banks to "
                  "replace withdrawn Gulf funding, which is the closest thing to an emergency "
                  "operation this central bank has run",),
    "root": "https://www.qcb.gov.qa",
}

#: THE OTHER THREE MONETARY AUTHORITIES. Kuwait is the one that is different in kind and it is
#: written out in full for exactly that reason.
CENTRAL_BANKS: dict[str, dict[str, Any]] = {
    "qa": {"name": "Qatar Central Bank", "framework": "peg", "root": "https://www.qcb.gov.qa",
           "rule": "tracks the Fed; the deviation is the observable"},
    "kw": {"name": "Central Bank of Kuwait -- بنك الكويت المركزي", "framework": "band",
           "root": "https://www.cbk.gov.kw",
           "rule": "THE ONLY ONE WITH DISCRETION. The CBK sets the dinar against an undisclosed "
                   "weighted basket and publishes a customer rate EVERY BUSINESS DAY, and it "
                   "sets its own discount rate -- in the 2022-2023 cycle it repeatedly moved by "
                   "less than the Fed, which a dollar peg cannot do. Both the fixing and the "
                   "discount rate are therefore real, separate events"},
    "om": {"name": "Central Bank of Oman -- البنك المركزي العماني", "framework": "peg",
           "root": "https://cbo.gov.om",
           "rule": "tracks the Fed through the repo rate; the CBO also runs the government's "
                   "Treasury-bill and sukuk programme, so its auctions are the local funding "
                   "clock the rating agencies read"},
    "bh": {"name": "Central Bank of Bahrain -- مصرف البحرين المركزي", "framework": "peg",
           "root": "https://www.cbb.gov.bh",
           "rule": "tracks the Fed through the one-week deposit rate; the CBB is ALSO the "
                   "licensing authority for the offshore wholesale banks, which is why its "
                   "published interbank rate carries regional information the others' do not"},
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Central Bank of Kuwait daily KWD customer rate (the basket fixing)",
     "local": "published each business day, Sunday to Thursday, Asia/Kuwait (UTC+3)",
     "time_utc": "06:00", "time_utc_dst": "06:00",
     "dst_rule": "none; Kuwait is UTC+3 all year",
     "instruments": ("USDX", "EURUSD", "USDJPY"), "window_minutes": 60,
     "why": "THE ONLY GULF FIXING THAT CARRIES INFORMATION. The basket weights are undisclosed, "
            "so the fixing is the CBK's own statement about the dollar's weight; the residual "
            "after regressing it on the majors is the measurable discretion"},
    {"name": "Qatar Central Bank riyal corridor (3.6385 bid / 3.6415 offer to banks)",
     "local": "standing; quoted continuously to licensed banks, Asia/Qatar",
     "time_utc": "07:00", "time_utc_dst": "07:00", "dst_rule": "none; UTC+3 all year",
     "instruments": ("USDX",), "window_minutes": 30,
     "why": "the onshore riyal is a corridor, not a price; declared so no study treats a 3.6400 "
            "print as a market outcome"},
    {"name": "Central Bank of Oman rial corridor (0.3844 buy / 0.3850 sell)",
     "local": "standing; quoted to licensed banks, Asia/Muscat (UTC+4)",
     "time_utc": "06:00", "time_utc_dst": "06:00", "dst_rule": "none; Oman is UTC+4 all year",
     "instruments": ("USDX",), "window_minutes": 30,
     "why": "the same corridor shape one hour earlier in UTC, the only intra-Gulf clock "
            "difference and the reason a pooled 'Gulf morning' window is two windows"},
    {"name": "Central Bank of Bahrain dinar corridor (0.3760 sell / 0.3770 buy)",
     "local": "standing; quoted to licensed banks, Asia/Bahrain (UTC+3)",
     "time_utc": "07:00", "time_utc_dst": "07:00", "dst_rule": "none; UTC+3 all year",
     "instruments": ("USDX",), "window_minutes": 30,
     "why": "the weakest peg in the GCC; the corridor holds and the stress appears in the "
            "forward points and the sovereign spread instead"},
    {"name": "DME / Gulf Mercantile Exchange Oman Crude marker settlement window",
     "local": "the Singapore afternoon marker window closing 16:30 Asia/Singapore",
     "time_utc": "08:30", "time_utc_dst": "08:30",
     "dst_rule": "none; Singapore keeps UTC+8 all year",
     "instruments": ("XBRUSD", "XTIUSD", "JPN225"), "window_minutes": 30,
     "why": "the Asian sour benchmark is STRUCK in this window, so the Brent-Dubai spread and "
            "every Asian refining margin has a dated minute rather than a daily average"},
    {"name": "Platts Dubai / Oman market-on-close assessment window",
     "local": "the same Singapore afternoon window", "time_utc": "08:30",
     "time_utc_dst": "08:30", "dst_rule": "none",
     "instruments": ("XBRUSD", "XTIUSD"), "window_minutes": 30,
     "why": "LICENSED GROUND, registered and never scraped: the assessment itself is paywalled, "
            "so the pack measures the exchange-traded leg and the refined-product outcome"},
    {"name": "Kuwaiti and Qatari official selling price (OSP) announcement",
     "local": "around the fifth of each month for the following month's liftings",
     "time_utc": "10:00", "time_utc_dst": "10:00", "dst_rule": "none",
     "instruments": ("XBRUSD", "XTIUSD", "USDINR"), "window_minutes": 120,
     "why": "KPC and QatarEnergy set differentials to the Oman/Dubai average for Asia and to "
            "other markers for the West; the announcement is an administered, dated event and "
            "therefore testable in a way a price is not"},
    {"name": "LBMA gold price PM auction (the Gulf retail gold reference)",
     "local": "15:00 Europe/London", "time_utc": "15:00", "time_utc_dst": "14:00",
     "dst_rule": "GMT/BST -- the ONE clock in this pack that moves, because the Gulf's does not",
     "instruments": ("XAUUSD", "XAGUSD"), "window_minutes": 15,
     "why": "the Gulf gold souks quote off the PM fix; the Eid and wedding-season demand of "
            "GULF-M is a physical flow into that price"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Monthly official selling price announcement (KPC, QatarEnergy)",
     "kind": "day_of_month", "days": (5,), "roll": "next", "window_utc": ("08:00", "12:00"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "why": "the Asian differentials are announced in the first week for the next month's "
            "liftings, after the Saudi OSP sets the reference"},
    {"name": "Qatari LNG monthly loading programme and the Ras Laffan berth schedule",
     "kind": "month_end", "roll": "previous", "window_utc": ("06:00", "12:00"),
     "instruments": ("XNGUSD", "XBRUSD"),
     "why": "cargo nominations and the loading programme are set into the month boundary; the "
            "physical counterpart of every Qatari gas claim in this pack"},
    {"name": "The GCC trading week: Sunday to Thursday, Friday-Saturday weekend",
     "kind": "weekday", "weekday": 6, "roll": "next", "window_utc": ("06:00", "10:15"),
     "instruments": ("USDX", "XBRUSD", "XAUUSD"),
     "why": "ALL FOUR of these states trade Sunday to Thursday, unlike the UAE since 2022-01-03; "
            "the Gulf Sunday session is the first cash market to price a weekend event and it "
            "closes before London opens"},
    {"name": "Kuwaiti fiscal year end, 31 March (the Future Generations Fund transfer)",
     "kind": "fiscal_year_end", "roll": "previous", "window_utc": ("06:00", "14:00"),
     "instruments": ("USDX", "US500", "UST10Y"),
     "why": "the 10%-of-revenue statutory transfer and the General Reserve Fund's liquidity "
            "position are struck on a March year end, a quarter away from its neighbours'"},
    {"name": "Calendar fiscal year end, 31 December (Qatar, Oman, Bahrain)",
     "kind": "fiscal_year_end", "roll": "previous", "window_utc": ("06:00", "14:00"),
     "instruments": ("USDX", "UST05Y"),
     "why": "the budget, the sovereign issuance plan and the subsidy envelope are dated to it"},
    {"name": "MSCI and FTSE Russell semi-annual and quarterly index reviews",
     "kind": "quarter_end", "roll": "previous", "window_utc": ("13:00", "16:30"),
     "instruments": ("US500", "UK100", "USDX"),
     "why": "the GCC upgrades (Qatar 2014, Kuwait 2019-2020) rebalanced global EM funds on "
            "DATED, PUBLISHED effective days -- the cleanest flow events this region produces, "
            "and the flow is denominated in dollars"},
    {"name": "Month-end expatriate remittance settlement through the exchange houses",
     "kind": "month_end", "roll": "previous", "window_utc": ("06:00", "13:00"),
     "instruments": ("USDINR", "USDSGD", "USDZAR"),
     "why": "the four states are majority-expatriate labour markets paid monthly; the salary and "
            "remittance cycle is a real, dated dollar-to-rupee flow"},
    {"name": "OPEC+ ministerial and JMMC meeting dates",
     "kind": "day_of_month", "days": (1, 2, 3, 4), "roll": "next",
     "window_utc": ("10:00", "16:00"), "instruments": ("XBRUSD", "XTIUSD"),
     "why": "the Declaration of Cooperation meets at the start of a month or in a called "
            "session; Oman is a DoC member and NOT an OPEC member, and Qatar left OPEC on "
            "2019-01-01, so the membership under the name has changed twice"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Qatar Stock Exchange (QE) -- بورصة قطر",
     "index_symbols": (),
     "open_local": "09:30", "close_local": "13:15", "open_utc": "06:30", "close_utc": "10:15",
     "dst_rule": "none; Asia/Qatar is UTC+3 all year",
     "auction": "pre-open from 09:00, continuous 09:30-13:00, closing auction to 13:15",
     "expiry_rule": "no listed index derivatives with a public tape; QE has run a securities "
                    "lending and covered short-selling framework since 2019 rather than a "
                    "futures market, so there is no expiry clock to mine",
     "holidays": "the Qatari national calendar and the sighted feasts; the session SHORTENS in "
                 "Ramadan, which is the one recurring session change in this pack",
     "notes": "NO CFD IS QUOTED on the QE Index; it enters as a transmission target. Qatar was "
              "upgraded to MSCI Emerging Markets in 2014, the dated inclusion event GULF-N "
              "studies"},
    {"name": "Boursa Kuwait -- بورصة الكويت",
     "index_symbols": (),
     "open_local": "09:00", "close_local": "12:30", "open_utc": "06:00", "close_utc": "09:30",
     "dst_rule": "none; Asia/Kuwait is UTC+3 all year",
     "auction": "opening auction 09:00, continuous to 12:30, closing auction",
     "expiry_rule": "no public index-derivative tape",
     "holidays": "the Kuwaiti national calendar (25-26 February) and the sighted feasts",
     "notes": "Kuwait's promotion to MSCI EM took effect in NOVEMBER 2020 after a COVID delay "
              "from May -- a DATED, PUBLISHED, RESCHEDULED rebalance, which makes it the best "
              "single inclusion event in the GCC because the delay itself is a placebo"},
    {"name": "Muscat Stock Exchange (MSX) -- بورصة مسقط",
     "index_symbols": (),
     "open_local": "10:00", "close_local": "13:00", "open_utc": "06:00", "close_utc": "09:00",
     "dst_rule": "none; Asia/Muscat is UTC+4 all year",
     "auction": "pre-open 09:30, continuous 10:00-13:00",
     "expiry_rule": "none listed with a public tape",
     "holidays": "the Omani national calendar (18 November) and the sighted feasts",
     "notes": "OMAN IS ONE HOUR AHEAD OF ITS THREE NEIGHBOURS, so the MSX opens at the same UTC "
              "minute as Boursa Kuwait and closes half an hour earlier; the exchange was "
              "restructured under the Oman Investment Authority in 2021"},
    {"name": "Bahrain Bourse -- بورصة البحرين",
     "index_symbols": (),
     "open_local": "09:30", "close_local": "13:00", "open_utc": "06:30", "close_utc": "10:00",
     "dst_rule": "none; Asia/Bahrain is UTC+3 all year",
     "auction": "opening auction 09:30, continuous to 13:00",
     "expiry_rule": "none listed with a public tape",
     "holidays": "the Bahraini national calendar (16-17 December) and the sighted feasts",
     "notes": "the smallest tape in the GCC and the one whose listed banks are regional rather "
              "than domestic; the bourse is an observable, never an instrument here"},
    {"name": "Dubai Mercantile Exchange / Gulf Mercantile Exchange (the Oman crude marker)",
     "index_symbols": (),
     "open_local": "electronic, nearly 24 hours", "close_local": "16:30 Asia/Singapore marker",
     "open_utc": "22:00", "close_utc": "08:30",
     "dst_rule": "none for the marker window; Singapore is UTC+8 all year",
     "auction": "the marker window closing 16:30 Singapore sets the settlement price",
     "expiry_rule": "the Oman contract expires two months before delivery, so the OSP "
                    "announcement in the first week of a month and the expiry are two different "
                    "clocks that a pooled study conflates",
     "holidays": "the exchange calendar, not a Gulf national one",
     "notes": "THE VENUE IS A FUTURES EXCHANGE, not a crypto venue, and it is named here as the "
              "settlement process behind a benchmark. No order book, feed or depth is used"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "gulf_cash_morning", "start_utc": "06:00", "end_utc": "10:15",
     "notes": "the union of the four cash sessions; it opens before Europe and closes before "
              "London's first hour is over, so a Gulf reaction is observable in isolation"},
    {"name": "gulf_sunday_lead", "start_utc": "06:00", "end_utc": "10:15",
     "notes": "THE SUNDAY SESSION. All four of these markets trade Sunday to Thursday, so a "
              "weekend event is priced in Doha, Kuwait, Muscat and Manama before any G10 cash "
              "market opens; the broker's own Sunday is closed, which is the whole point of "
              "treating this as an INFORMATION window and not a trading one"},
    {"name": "msx_muscat", "start_utc": "06:00", "end_utc": "09:00",
     "notes": "Oman is UTC+4, so its local 10:00 open is the same UTC minute as Kuwait's 09:00"},
    {"name": "dme_oman_marker", "start_utc": "08:15", "end_utc": "08:45",
     "notes": "the Singapore-afternoon settlement window for the Asian sour benchmark"},
    {"name": "gulf_osp_window", "start_utc": "09:00", "end_utc": "12:00",
     "notes": "the first-week-of-month OSP announcements, after the Saudi reference lands"},
    {"name": "gulf_fomc_echo", "start_utc": "19:00", "end_utc": "21:00",
     "notes": "the evening in which three of the four central banks publish the circular that "
              "matches (or does not match) the Fed's step"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "CBK daily KWD customer rate against the basket", "cadence": "daily",
     "time_utc": "06:00", "source": "Central Bank of Kuwait",
     "actual_series": "CBK:kwd_usd_daily", "expected_series": "UNMEASURED",
     "notes": "every business day Sunday-Thursday; the only Gulf FX print with information"},
    {"name": "QatarEnergy North Field project and train milestones", "cadence": "irregular",
     "time_utc": "10:00", "source": "QatarEnergy", "actual_series": "QE:nf_capacity_mtpa",
     "expected_series": "n/a",
     "notes": "FID, EPC award, first-cargo and capacity-step announcements; the dated supply "
              "curve GULF-A is built on"},
    {"name": "Kuwaiti and Qatari monthly official selling prices", "cadence": "monthly",
     "time_utc": "10:00", "source": "KPC / QatarEnergy",
     "actual_series": "KPC:osp_asia_differential", "expected_series": "UNMEASURED",
     "notes": "the first week of the month, after Saudi Aramco's OSP sets the reference"},
    {"name": "OPEC Monthly Oil Market Report: Kuwaiti, Omani and Bahraini production",
     "cadence": "monthly", "time_utc": "11:00", "source": "OPEC Secretariat",
     "actual_series": "OPEC:mom_production", "expected_series": "UNMEASURED",
     "notes": "secondary-source estimates; Oman appears as a NON-OPEC DoC participant and Qatar "
              "left OPEC on 2019-01-01, so the table's membership changed under the name"},
    {"name": "Qatar Planning and Statistics Authority CPI, trade and LNG export volumes",
     "cadence": "monthly", "time_utc": "08:00", "source": "PSA Qatar",
     "actual_series": "PSA:trade_exports", "expected_series": "UNMEASURED",
     "notes": "the monthly trade bulletin carries LNG export VALUE and destination, which is the "
              "only public read on realised Qatari contract pricing"},
    {"name": "Central Bank of Kuwait monetary statistics and the discount rate circular",
     "cadence": "monthly", "time_utc": "07:00", "source": "CBK",
     "actual_series": "CBK:discount_rate", "expected_series": "FOMC:target_range",
     "notes": "the CBK has moved by LESS than the Fed in the same cycle, which no dollar peg can "
              "do; the gap is the measurable discretion"},
    {"name": "Central Bank of Oman weekly Treasury-bill and monthly sukuk auctions",
     "cadence": "weekly", "time_utc": "06:00", "source": "CBO",
     "actual_series": "CBO:tbill_cutoff", "expected_series": "UNMEASURED",
     "notes": "the local funding clock the rating agencies read through the 2020-2021 stress"},
    {"name": "Central Bank of Bahrain interbank rate and the weekly Treasury-bill auction",
     "cadence": "weekly", "time_utc": "07:00", "source": "CBB",
     "actual_series": "CBB:bhibor_3m", "expected_series": "UNMEASURED",
     "notes": "the BHIBOR-minus-SOFR spread is the region's cheapest public stress gauge"},
    {"name": "NCSI Oman monthly bulletin: crude production, exports by destination, prices",
     "cadence": "monthly", "time_utc": "06:00",
     "source": "National Centre for Statistics and Information, Oman",
     "actual_series": "NCSI:crude_exports", "expected_series": "n/a",
     "notes": "Oman publishes production AND its realised average price monthly, the most "
              "transparent oil series in the Gulf and the reason GULF-G is testable"},
    {"name": "GCC-Stat regional statistics (the four states on one comparable basis)",
     "cadence": "quarterly", "time_utc": "09:00", "source": "GCC Statistical Centre",
     "actual_series": "GCCSTAT:gdp_cpi_trade", "expected_series": "n/a",
     "notes": "the only publisher that harmonises all six members' definitions, which is what "
              "makes a CROSS-STATE control in this pack honest rather than approximate"},
)

# --------------------------------------------------------------------------- holidays and clocks
#: THE WEEKEND IS FRIDAY AND SATURDAY IN ALL FOUR STATES, and it has been throughout the sample.
#: The UAE left this weekend on 2022-01-03 and Saudi Arabia left the Thursday-Friday weekend in
#: 2013; these four did neither, so `ae`'s working-week break does NOT apply here and a study
#: that inherits it from the sibling pack is aligning sessions that were never misaligned.
WEEKEND_WEEKDAYS: tuple[int, int] = (4, 5)     # Python weekday(): Friday = 4, Saturday = 5

#: FIXED SOLAR NATIONAL DAYS, PER JURISDICTION, derived by `national_holidays`. These are the
#: rows a rule can compute, so none of them is typed twice. Qatar's New Year is deliberately
#: ABSENT: 1 January is not a statutory Qatari public holiday, it is a BANK closure, and the
#: distinction is the difference between a closed exchange and a closed settlement system.
FIXED_NATIONAL: dict[str, tuple[tuple[int, int, str], ...]] = {
    "qa": ((12, 18, "Qatar National Day / اليوم الوطني لدولة قطر"),),
    "kw": ((1, 1, "New Year / رأس السنة الميلادية"),
           (2, 25, "Kuwait National Day / العيد الوطني الكويتي"),
           (2, 26, "Liberation Day / يوم التحرير")),
    "om": ((1, 1, "New Year / رأس السنة الميلادية"),
           (7, 23, "Renaissance Day / يوم النهضة"),
           (11, 18, "Oman National Day / العيد الوطني العماني")),
    "bh": ((1, 1, "New Year / رأس السنة الميلادية"),
           (5, 1, "Labour Day / عيد العمال"),
           (12, 16, "Bahrain National Day / العيد الوطني البحريني"),
           (12, 17, "Bahrain National Day (day 2) / العيد الوطني البحريني")),
}

#: QATAR'S SECOND NATIONAL HOLIDAY IS A DERIVED WEEKDAY RULE and therefore is NOT typed: National
#: Sports Day (اليوم الرياضي للدولة) is the SECOND TUESDAY OF FEBRUARY by Emiri decision, a
#: full public holiday, and the only Gulf national holiday in this pack that moves within the
#: solar year. `qatar_sports_day(year)` computes it.
SPORTS_DAY_WEEKDAY = 1        # Tuesday
SPORTS_DAY_ORDINAL = 2        # the second one in February

#: WHO SIGHTS THE MOON, BY STATE. This is the field the lunar table's `status` carries, because a
#: Hijri date is not a calculation -- it is an ANNOUNCEMENT by a named committee on the evening
#: before, and the four committees do not always agree.
SIGHTING_AUTHORITIES: dict[str, str] = {
    "qa": "دار التقويم القطري ولجنة تحري الهلال بوزارة الأوقاف والشؤون الإسلامية (Qatar Calendar "
          "House and the Awqaf crescent committee)",
    "kw": "لجنة استطلاع الأهلة بوزارة الأوقاف والشؤون الإسلامية (the Kuwaiti Awqaf "
          "crescent-sighting committee)",
    "om": "لجنة تحري الأهلة بوزارة الأوقاف والشؤون الدينية (the Omani committee, which SIGHTS "
          "INDEPENDENTLY and has landed one day after its neighbours in several years)",
    "bh": "لجنة تحري الهلال بوزارة العدل والشؤون الإسلامية والأوقاف (the Bahraini committee)",
}


def sighting_status(kind: str) -> str:
    """The `status` string a lunar row carries: the confidence label AND the named authority for
    each of the four states. A Hijri date is an announcement, not an algorithm, and this is how
    the table says so on every row instead of once in a footnote."""
    named = "; ".join(f"{cc}={SIGHTING_AUTHORITIES[cc]}" for cc in JURISDICTIONS)
    return f"{kind} -- sighted and announced by: {named}"


#: THE MOON-SIGHTED FEASTS, TYPED. There is NO weekday rule and no arithmetic that produces these
#: dates: the committees above announce them the evening before, and an algorithm that "computes"
#: a Hijri date produces a number that is frequently one day wrong -- which, for an event study
#: whose whole content is the day, is the difference between a result and a mislabelled sample.
#: So they are TYPED for 2024, 2025 and 2026, each row carrying the four authorities in `status`,
#: and the 2026 rows say PROJECTED because a 2026 sighting has not happened.
#: Row: (date, name, jurisdictions that close, status).
LUNAR_HOLIDAYS: dict[int, tuple[tuple[date, str, tuple[str, ...], str], ...]] = {
    2024: (
        (date(2024, 2, 8), "Isra wal Mi'raj / الإسراء والمعراج", ("kw", "om"),
         sighting_status("ANNOUNCED")),
        (date(2024, 3, 11), "First day of Ramadan / أول أيام رمضان", ("qa", "kw", "om", "bh"),
         sighting_status("ANNOUNCED (not a closure; the SESSION SHORTENS)")),
        (date(2024, 4, 10), "Eid al-Fitr day 1 / عيد الفطر", ("qa", "kw", "om", "bh"),
         sighting_status("ANNOUNCED")),
        (date(2024, 4, 11), "Eid al-Fitr day 2 / عيد الفطر", ("qa", "kw", "om", "bh"),
         sighting_status("ANNOUNCED")),
        (date(2024, 4, 12), "Eid al-Fitr day 3 / عيد الفطر", ("qa", "kw", "om", "bh"),
         sighting_status("ANNOUNCED")),
        (date(2024, 6, 16), "Eid al-Adha day 1 / عيد الأضحى", ("qa", "kw", "om", "bh"),
         sighting_status("ANNOUNCED")),
        (date(2024, 6, 17), "Eid al-Adha day 2 / عيد الأضحى", ("qa", "kw", "om", "bh"),
         sighting_status("ANNOUNCED")),
        (date(2024, 6, 18), "Eid al-Adha day 3 / عيد الأضحى", ("qa", "kw", "om", "bh"),
         sighting_status("ANNOUNCED")),
        (date(2024, 7, 7), "Hijri New Year 1446 / رأس السنة الهجرية", ("kw", "om", "bh"),
         sighting_status("ANNOUNCED")),
        (date(2024, 7, 15), "Ashura day 1 / عاشوراء", ("bh",),
         sighting_status("ANNOUNCED -- BAHRAIN ONLY")),
        (date(2024, 7, 16), "Ashura day 2 / عاشوراء", ("bh",),
         sighting_status("ANNOUNCED -- BAHRAIN ONLY")),
        (date(2024, 9, 15), "Prophet's Birthday / المولد النبوي", ("om", "bh"),
         sighting_status("ANNOUNCED")),
    ),
    2025: (
        (date(2025, 1, 27), "Isra wal Mi'raj / الإسراء والمعراج", ("kw", "om"),
         sighting_status("ANNOUNCED")),
        (date(2025, 3, 1), "First day of Ramadan / أول أيام رمضان", ("qa", "kw", "om", "bh"),
         sighting_status("ANNOUNCED (not a closure; the SESSION SHORTENS)")),
        (date(2025, 3, 30), "Eid al-Fitr day 1 / عيد الفطر", ("qa", "kw", "om", "bh"),
         sighting_status("ANNOUNCED")),
        (date(2025, 3, 31), "Eid al-Fitr day 2 / عيد الفطر", ("qa", "kw", "om", "bh"),
         sighting_status("ANNOUNCED")),
        (date(2025, 4, 1), "Eid al-Fitr day 3 / عيد الفطر", ("qa", "kw", "om", "bh"),
         sighting_status("ANNOUNCED")),
        (date(2025, 6, 5), "Day of Arafat / يوم عرفة", ("kw", "om"),
         sighting_status("ANNOUNCED")),
        (date(2025, 6, 6), "Eid al-Adha day 1 / عيد الأضحى", ("qa", "kw", "om", "bh"),
         sighting_status("ANNOUNCED")),
        (date(2025, 6, 9), "Eid al-Adha day 3 (observed) / عيد الأضحى", ("qa", "kw", "om", "bh"),
         sighting_status("ANNOUNCED")),
        (date(2025, 6, 26), "Hijri New Year 1447 / رأس السنة الهجرية", ("kw", "om", "bh"),
         sighting_status("ANNOUNCED")),
        (date(2025, 7, 4), "Ashura day 1 / عاشوراء", ("bh",),
         sighting_status("ANNOUNCED -- BAHRAIN ONLY")),
        (date(2025, 7, 5), "Ashura day 2 / عاشوراء", ("bh",),
         sighting_status("ANNOUNCED -- BAHRAIN ONLY")),
        (date(2025, 9, 4), "Prophet's Birthday / المولد النبوي", ("om", "bh"),
         sighting_status("ANNOUNCED")),
    ),
    2026: (
        (date(2026, 1, 16), "Isra wal Mi'raj / الإسراء والمعراج", ("kw", "om"),
         sighting_status("PROJECTED")),
        (date(2026, 2, 18), "First day of Ramadan / أول أيام رمضان", ("qa", "kw", "om", "bh"),
         sighting_status("PROJECTED (not a closure; the SESSION SHORTENS)")),
        (date(2026, 3, 19), "Eid al-Fitr day 1 / عيد الفطر", ("qa", "kw", "om", "bh"),
         sighting_status("PROJECTED")),
        (date(2026, 3, 20), "Eid al-Fitr day 2 / عيد الفطر", ("qa", "kw", "om", "bh"),
         sighting_status("PROJECTED")),
        (date(2026, 3, 21), "Eid al-Fitr day 3 / عيد الفطر", ("qa", "kw", "om", "bh"),
         sighting_status("PROJECTED")),
        (date(2026, 5, 26), "Eid al-Adha day 1 / عيد الأضحى", ("qa", "kw", "om", "bh"),
         sighting_status("PROJECTED")),
        (date(2026, 5, 27), "Eid al-Adha day 2 / عيد الأضحى", ("qa", "kw", "om", "bh"),
         sighting_status("PROJECTED")),
        (date(2026, 5, 28), "Eid al-Adha day 3 / عيد الأضحى", ("qa", "kw", "om", "bh"),
         sighting_status("PROJECTED")),
        (date(2026, 6, 16), "Hijri New Year 1448 / رأس السنة الهجرية", ("kw", "om", "bh"),
         sighting_status("PROJECTED")),
        (date(2026, 6, 24), "Ashura day 1 / عاشوراء", ("bh",),
         sighting_status("PROJECTED -- BAHRAIN ONLY")),
        (date(2026, 6, 25), "Ashura day 2 / عاشوراء", ("bh",),
         sighting_status("PROJECTED -- BAHRAIN ONLY")),
        (date(2026, 8, 24), "Prophet's Birthday / المولد النبوي", ("om", "bh"),
         sighting_status("PROJECTED")),
    ),
}

#: THE RAMADAN SESSION WINDOW, per year: (first day, last day before Eid, status). Inside it the
#: four exchanges SHORTEN their sessions and the working day moves; the closure is Eid, but the
#: liquidity change is the whole month, and a study that only dummies the three Eid days has
#: mislabelled about thirty sessions as normal.
RAMADAN_WINDOWS: dict[int, tuple[date, date, str]] = {
    2024: (date(2024, 3, 11), date(2024, 4, 9), "ANNOUNCED"),
    2025: (date(2025, 3, 1), date(2025, 3, 29), "ANNOUNCED"),
    2026: (date(2026, 2, 18), date(2026, 3, 18), "PROJECTED"),
}

#: ONE-OFF CLOSURES AND DATED FACTS NO RULE PRODUCES.
DECLARED_CLOSURES: dict[date, str] = {
    date(2024, 12, 18): "Qatar National Day on a Wednesday: the QE, the QCB and the banks closed",
    date(2025, 2, 25): "Kuwait National Day on a Tuesday, followed by Liberation Day on the "
                       "Wednesday: Boursa Kuwait lost two mid-week sessions",
    date(2025, 11, 18): "Oman National Day on a Tuesday; Oman moved its National Day from 18-19 "
                        "November to a single 18 November observance under Sultan Haitham",
}

#: THE OPEC+ DECISION CLOCK, TYPED, because the Declaration of Cooperation does not meet on a
#: rule. Row: (date, what, status). The 2020-03-06 row is the one that matters most: it is the
#: day the DoC FAILED and the price war began, and it is the single largest dated oil event in
#: the sample this pack can reach.
OPEC_PLUS_DATES: tuple[tuple[date, str, str], ...] = (
    (date(2020, 3, 6), "the DoC breaks down; no agreement with Russia and the price war begins",
     "HISTORICAL"),
    (date(2020, 4, 12), "the record 9.7 mb/d cut agreed after an emergency session",
     "HISTORICAL"),
    (date(2021, 7, 18), "the UAE baseline dispute resolved; quotas re-based", "HISTORICAL"),
    (date(2022, 10, 5), "the 2 mb/d headline cut agreed in Vienna", "HISTORICAL"),
    (date(2023, 4, 2), "the surprise Sunday voluntary cuts announced outside a meeting",
     "HISTORICAL"),
    (date(2023, 6, 4), "Angola and Nigeria baselines reset; Saudi's unilateral extra cut",
     "HISTORICAL"),
    (date(2024, 6, 2), "the voluntary-cut unwind path published to 2025", "HISTORICAL"),
    (date(2024, 12, 5), "the unwind deferred again to 2025-04", "HISTORICAL"),
    (date(2025, 3, 3), "the eight voluntary producers confirm the April start of the unwind",
     "PRESS_REPORTED"),
)


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The n-th `weekday` (Monday = 0) of a month -- the shape Qatar's Sports Day takes."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return date(year, month, 1 + offset + 7 * (n - 1))


def qatar_sports_day(year: int) -> date:
    """Qatar National Sports Day: the SECOND TUESDAY OF FEBRUARY, derived and never typed.

    This is the one Gulf national holiday in this pack that a rule can compute, and it is
    computed: 2024-02-13, 2025-02-11, 2026-02-10.
    """
    return nth_weekday(year, 2, SPORTS_DAY_WEEKDAY, SPORTS_DAY_ORDINAL)


def national_day(code: str, year: int) -> tuple[date, ...]:
    """The fixed solar national days of one jurisdiction in a year, DERIVED from FIXED_NATIONAL
    plus Qatar's computed Sports Day. Qatar 18 December, Kuwait 25-26 February, Oman 18 November
    and 23 July, Bahrain 16-17 December -- none of them typed into a year table."""
    cc = str(code).lower()
    out = [date(year, m, d) for m, d, _n in FIXED_NATIONAL.get(cc, ())]
    if cc == "qa":
        out.append(qatar_sports_day(year))
    return tuple(sorted(out))


def national_holidays(year: int) -> dict[date, str]:
    """Every closed day across the four states in a year, with the states that close on it.

    THE FIXED DAYS ARE DERIVED and the moon-sighted days are TYPED, which is the honest split:
    18 December is 18 December in every year, and no arithmetic knows when the crescent was
    seen. No weekend substitution exists in any of the four: a national day on a Friday is lost.
    """
    rows: dict[date, list[str]] = {}
    for cc in JURISDICTIONS:
        for m, d, name in FIXED_NATIONAL.get(cc, ()):
            rows.setdefault(date(year, m, d), []).append(f"{cc}:{name}")
        if cc == "qa":
            rows.setdefault(qatar_sports_day(year), []).append(
                "qa:Qatar National Sports Day / اليوم الرياضي للدولة")
    for day, name, ccs, status in LUNAR_HOLIDAYS.get(year, ()):
        label = "ANNOUNCED" if status.startswith("ANNOUNCED") else "PROJECTED"
        rows.setdefault(day, []).append(f"{','.join(ccs)}:{name} [{label}]")
    for day, name in DECLARED_CLOSURES.items():
        if day.year == year:
            rows.setdefault(day, []).append(name)
    return {d: " | ".join(v) for d, v in sorted(rows.items())}


def market_holidays(year: int) -> dict[date, str]:
    """Closed days that actually COST A SESSION: the national calendar minus Friday and Saturday.

    The Gulf weekend is Friday-Saturday, so the weekday filter here is the OPPOSITE of the one
    every European pack uses. A holiday-liquidity study that inherits a Saturday-Sunday weekend
    from a sibling pack drops the wrong two days and keeps the wrong two.
    """
    return {d: n for d, n in national_holidays(year).items()
            if d.weekday() not in WEEKEND_WEEKDAYS}


def holidays_for(code: str, year: int) -> dict[date, str]:
    """One jurisdiction's own closed days. A Bahraini Ashura closure is not a Qatari one, and a
    pooled 'GCC holiday' dummy that closes all four on it is wrong three times out of four."""
    cc = str(code).lower()
    out: dict[date, str] = {}
    for m, d, name in FIXED_NATIONAL.get(cc, ()):
        out[date(year, m, d)] = name
    if cc == "qa":
        out[qatar_sports_day(year)] = "Qatar National Sports Day / اليوم الرياضي للدولة"
    for day, name, ccs, _status in LUNAR_HOLIDAYS.get(year, ()):
        if cc in ccs:
            out[day] = name
    return dict(sorted(out.items()))


def is_gcc_session_day(day: date) -> bool:
    """True when the four cash markets are open on a weekday basis: Sunday to Thursday.

    Python's `weekday()` is Monday=0..Sunday=6, so the Gulf business week is {6, 0, 1, 2, 3} and
    the weekend is {4, 5}. This is the single most commonly inverted fact about these markets.
    """
    return day.weekday() not in WEEKEND_WEEKDAYS


def gcc_session_days(start: date, end: date) -> list[date]:
    """Every Gulf business day in [start, end] that is not a market holiday in any of the four."""
    closed = {d for y in range(start.year, end.year + 1) for d in market_holidays(y)}
    out: list[date] = []
    day = start
    while day <= end:
        if is_gcc_session_day(day) and day not in closed:
            out.append(day)
        day = date.fromordinal(day.toordinal() + 1)
    return out


def ramadan_window(year: int) -> tuple[date, date, str] | None:
    """The declared Ramadan session window for a year, or None when the pack has not declared
    it. Inside it the four exchanges shorten their sessions."""
    return RAMADAN_WINDOWS.get(year)


def in_ramadan(day: date) -> bool:
    """True when this date falls inside a declared Ramadan window (a SHORTENED session)."""
    got = RAMADAN_WINDOWS.get(day.year)
    return got is not None and got[0] <= day <= got[1]


def opec_plus_dates(status: str = "") -> list[date]:
    """The typed OPEC+ decision dates, optionally filtered to one confidence label."""
    return [d for d, _what, st in OPEC_PLUS_DATES if not status or st == status]


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "derived_fixed_days_plus_typed_sightings",
    "authority": "each state's own moon-sighting committee announces the feasts the EVENING "
                 "BEFORE, and the four do not always agree -- Oman's committee sights "
                 "independently and has landed one day after its neighbours; the fixed national "
                 "days are set by decree and never move",
    "rule": "TWO KINDS OF DAY, AND THEY ARE TREATED DIFFERENTLY ON PURPOSE. (1) THE FIXED SOLAR "
            "DAYS ARE DERIVED, never typed into a year table: Qatar National Day 18 December, "
            "Kuwait National Day 25 February and Liberation Day 26 February, Oman National Day "
            "18 November and Renaissance Day 23 July, Bahrain National Day 16-17 December, New "
            "Year 1 January (Kuwait, Oman, Bahrain -- NOT a statutory Qatari holiday, only a "
            "bank closure) and Bahrain's Labour Day 1 May, plus Qatar's National Sports Day, "
            "which is the SECOND TUESDAY OF FEBRUARY and is computed by `qatar_sports_day`. "
            "(2) THE ISLAMIC-CALENDAR FEASTS CANNOT BE COMPUTED AND ARE NOT: Eid al-Fitr, Eid "
            "al-Adha, the Day of Arafat, the Hijri New Year, Ashura (BAHRAIN ONLY), Isra wal "
            "Mi'raj and the Prophet's Birthday are fixed by a SIGHTING announced the evening "
            "before, so they are TYPED for 2024, 2025 and 2026 and every row's `status` names "
            "the sighting authority of each of the four states. A weekday rule that pretends to "
            "produce them would be wrong by a day often enough to mislabel the event sample it "
            "exists to build; an honest typed table beats a wrong algorithm. THE WEEKEND IS "
            "FRIDAY AND SATURDAY in all four states, so the session-costing filter drops "
            "weekday() 4 and 5 and NOT 5 and 6. There is NO weekend substitution: a national "
            "day that falls on a Friday is lost.",
    "years": (2024, 2025, 2026),
    "weekend": "Friday and Saturday (weekday 4 and 5)",
    "national_rule": "see `rule`; `national_holidays(year)` is the derived-plus-typed union and "
                     "`holidays_for(code, year)` is one state's own calendar",
    "market_rule": "the union on Sunday-Thursday only; the QE, Boursa Kuwait, MSX and Bahrain "
                   "Bourse each keep their own subset and `holidays_for` is how they are split",
    "moon_sighting_rule": "DECLARED, not inferred. ANNOUNCED rows are what the committees "
                          "announced; PROJECTED rows may be one day off; Oman's independent "
                          "sighting is the most frequent source of a one-day split inside the "
                          "GCC and a Saudi or Moroccan calendar is the wrong calendar for it",
    "moving_feasts": "the lunar feasts drift about eleven days earlier each solar year, so the "
                     "Ramadan liquidity season walks through the whole solar calendar in 33 "
                     "years and no month-of-year dummy can absorb it",
    "ramadan_rule": "the four exchanges SHORTEN their sessions for the month; the closure is "
                    "Eid but the liquidity change is the month, see RAMADAN_WINDOWS",
    "table": {y: {d.isoformat(): n for d, n in national_holidays(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {
        2024: sighting_status("ANNOUNCED for every lunar row; the fixed days are certain"),
        2025: sighting_status("ANNOUNCED for every lunar row; the fixed days are certain"),
        2026: sighting_status("PROJECTED for every lunar row -- a 2026 sighting has not "
                              "happened and cannot be announced; the fixed days are certain"),
    },
    "known_dates": {
        "2024-04-10": "Eid al-Fitr day 1 across all four states as announced",
        "2024-06-16": "Eid al-Adha day 1; the Day of Arafat was 15 June",
        "2025-03-30": "Eid al-Fitr day 1 (a Sunday, so the Gulf lost a session the G10 did not)",
        "2025-06-06": "Eid al-Adha day 1; Arafat 5 June",
        "2026-02-10": "Qatar National Sports Day, DERIVED as the second Tuesday of February",
        "2026-03-19": "PROJECTED Eid al-Fitr day 1; the announced date can differ by a day",
        "2026-12-18": "Qatar National Day, a fixed solar date and certain in every year",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "per_country_fn": holidays_for,
    "sports_day_fn": qatar_sports_day,
    "ramadan_fn": ramadan_window,
    "session_day_fn": is_gcc_session_day,
}


# ------------------------------------------------------------------- the pack's own mechanisms
#: THE NORTH FIELD SCHEDULE AS A FUNCTION OF THE YEAR. These are the ANNOUNCED nameplate steps,
#: not a forecast: 77 mtpa today, North Field East to 110, North Field South to 126, North Field
#: West to 142 by 2030. Row: (first year the capacity is claimed, mtpa, project, status).
NORTH_FIELD_SCHEDULE: tuple[tuple[int, float, str, str], ...] = (
    (2010, 77.0, "the Qatargas/RasGas build-out completed; a 77 mtpa plateau and a moratorium "
                 "on further North Field development from 2005", "HISTORICAL"),
    (2026, 110.0, "North Field East (NFE): four trains, the moratorium lifted in 2017 and FID "
                  "taken in 2021", "ANNOUNCED_SCHEDULE"),
    (2027, 126.0, "North Field South (NFS): two further trains", "ANNOUNCED_SCHEDULE"),
    (2030, 142.0, "North Field West (NFW): announced 2024, taking the plateau to 142 mtpa",
     "ANNOUNCED_SCHEDULE"),
)


def north_field_capacity(year: int) -> float:
    """Qatar's ANNOUNCED LNG nameplate capacity, in mtpa, for a calendar year.

    This is the pack's first mechanism function and the reason Qatar is worth its trial budget:
    it is a PUBLISHED MULTI-YEAR SUPPLY CURVE with dates on it. 2024 -> 77.0, 2026 -> 110.0,
    2027 -> 126.0, 2030 -> 142.0. A schedule slips, and when one does the slip is itself the
    event -- which is why the rows carry ANNOUNCED_SCHEDULE and not a verified status.
    """
    out = 0.0
    for first_year, mtpa, _project, _status in NORTH_FIELD_SCHEDULE:
        if year >= first_year:
            out = mtpa
    return out


def peg_band_state(currency: str, rate: float) -> dict[str, Any]:
    """Where a quoted local rate sits inside its declared band. The pack's second mechanism.

    THREE OF THE FOUR ANSWER AND ONE REFUSES. QAR, OMR and BHD have published intervention
    corridors, so a rate maps to AT_STRONG_EDGE / INSIDE / AT_WEAK_EDGE / OUTSIDE with a distance
    in basis points. KWD has NO published band because its basket is undisclosed, so this
    returns UNMEASURED naming the reason rather than inventing a corridor -- absence is a
    measurement and never a default (L1.28a).
    """
    ccy = str(currency).upper()
    row = CURRENCIES.get(ccy)
    if row is None:
        return {"currency": ccy, "state": "UNMEASURED",
                "why": f"{ccy} is not one of the four currencies this pack answers for"}
    band = tuple(row.get("band") or ())
    if len(band) != 2:
        return {"currency": ccy, "regime": str(row["regime"]), "state": "UNMEASURED",
                "why": "the Central Bank of Kuwait's basket weights are UNDISCLOSED, so no "
                       "intervention corridor exists to measure a distance against; use "
                       "`kwd_basket_beta` on the published daily fixings instead"}
    lo, hi = float(band[0]), float(band[1])
    mid = float(row["mid"])
    value = float(rate)
    if value < lo or value > hi:
        state = "OUTSIDE"
    elif value <= lo + (hi - lo) * 0.05:
        state = "AT_STRONG_EDGE"
    elif value >= hi - (hi - lo) * 0.05:
        state = "AT_WEAK_EDGE"
    else:
        state = "INSIDE"
    return {"currency": ccy, "regime": str(row["regime"]), "mid": mid, "band": (lo, hi),
            "rate": value, "state": state,
            "distance_bp": round((value - mid) / mid * 10000.0, 4),
            "why": str(row["fact"])}


def kwd_basket_beta(rows: Sequence[tuple[float, float]]) -> dict[str, Any]:
    """Estimate the dollar's weight in Kuwait's UNDISCLOSED basket from the published fixings.

    THIS IS THE ONE GULF FX QUESTION THAT IS A QUESTION. `rows` are (kwd_per_usd, eurusd) pairs
    in date order, taken from the CBK's daily customer rate and any dollar cross. Regressing the
    log change of the dinar's dollar price on the log change of EURUSD recovers the non-dollar
    weight: if the basket were pure dollars the slope would be zero, and the published behaviour
    of the dinar is a small but persistent positive slope. Fewer than three usable observations
    answers UNMEASURED with the count, never a number.
    """
    pairs = [(float(a), float(b)) for a, b in rows if float(a) > 0.0 and float(b) > 0.0]
    if len(pairs) < 4:
        return {"measured": False, "n": len(pairs),
                "why": "UNMEASURED: fewer than four usable daily fixings; a basket weight "
                       "estimated on three points is a number with no standard error"}
    dk: list[float] = []
    de: list[float] = []
    for (k0, e0), (k1, e1) in pairwise(pairs):
        dk.append(_log(k1) - _log(k0))
        de.append(_log(e1) - _log(e0))
    n = float(len(dk))
    mean_x = sum(de) / n
    mean_y = sum(dk) / n
    sxx = sum((x - mean_x) ** 2 for x in de)
    if sxx <= 0.0:
        return {"measured": False, "n": len(dk),
                "why": "UNMEASURED: EURUSD did not move across the sample, so the regressor has "
                       "no variance and no weight is identified"}
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(de, dk, strict=True))
    beta = sxy / sxx
    # the dinar is quoted as KWD per USD, so a POSITIVE slope on EURUSD means the dinar follows
    # the euro and the basket is not pure dollar; the implied non-USD weight is the slope itself
    return {"measured": True, "n": len(dk), "beta_eurusd": round(beta, 6),
            "implied_non_usd_weight": round(beta, 6),
            "implied_usd_weight": round(1.0 - beta, 6),
            "why": "the slope of d log(KWD/USD) on d log(EURUSD); zero would mean a pure dollar "
                   "peg and the CBK has never published the true weights"}


def _log(x: float) -> float:
    """A local natural log, named so the regression above reads as arithmetic and not as a
    dependency: this module imports nothing heavier than the standard library."""
    return math.log(x)


def hormuz_bypass_share(port: str) -> dict[str, Any]:
    """Whether a named Gulf loading point sits INSIDE or OUTSIDE the Strait of Hormuz.

    This is the control that makes GULF-L a mechanism rather than a headline: Duqm, Ras Markaz
    and Sohar load on the Arabian Sea, so a strait event that moves Qatari and Kuwaiti loadings
    and does NOT move Omani ones is a chokepoint event, while one that moves both is a price
    event. Fujairah belongs to the sibling `ae` pack and is named here as the other bypass.
    """
    key = str(port).strip().lower()
    return {"port": port, "inside_hormuz": bool(HORMUZ_PORTS.get(key, True)),
            "known": key in HORMUZ_PORTS,
            "why": HORMUZ_PORTS_WHY.get(key, "UNMEASURED: this port is not in the pack's table, "
                                              "and an unknown port is not assumed to bypass")}


#: True means the cargo must transit the Strait of Hormuz to reach open water.
HORMUZ_PORTS: dict[str, bool] = {
    "ras laffan": True, "mesaieed": True, "halul": True,          # Qatar: all inside
    "mina al-ahmadi": True, "mina abdullah": True, "mina al-zour": True,   # Kuwait: all inside
    "sitra": True, "bapco": True,                                  # Bahrain: inside
    "duqm": False, "ras markaz": False, "sohar": False, "salalah": False,  # Oman: outside
    "mina al-fahal": True,                                         # Oman's OLD terminal: inside
    "fujairah": False,                                             # UAE's bypass (`ae` pack)
}
HORMUZ_PORTS_WHY: dict[str, str] = {
    "ras laffan": "every Qatari LNG cargo in the world transits Hormuz from here; there is no "
                  "Qatari bypass and no pipeline alternative",
    "duqm": "on the Arabian Sea, 600 km outside the strait; the refinery and the Ras Markaz "
            "crude reserve exist to be reachable when the strait is not",
    "ras markaz": "Oman's strategic crude storage, deliberately sited outside the strait",
    "sohar": "on the Gulf of Oman side; the only large Gulf industrial port with open-sea access",
    "mina al-fahal": "Oman's historic loading terminal IS inside the strait, which is precisely "
                     "why Duqm and Ras Markaz were built",
    "mina al-ahmadi": "Kuwait's main crude terminal, entirely dependent on the strait",
    "sitra": "Bahrain's refinery terminal, inside the strait and fed by the AB pipeline from "
             "Saudi Arabia",
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "Qatar Stock Exchange trading by nationality and by investor type",
     "root": "https://www.qe.com.qa/trading-by-nationality",
     "fields": ("foreign_individual_buy_sell", "foreign_institution_buy_sell",
                "qatari_individual_buy_sell", "qatari_institution_buy_sell", "net_foreign_qar"),
     "frequency": "daily", "snapshot": "each session", "publish_utc": "11:00", "lag_days": 0,
     "licence": "free, public", "available": True,
     "why": "A DAILY NET FOREIGN FLOW NUMBER, which is rarer than it sounds: the QE splits every "
            "session's turnover into Qatari and foreign, individual and institutional, and the "
            "net foreign line is a real positioning series for a country whose index no CFD "
            "quotes. It is the flow leg of GULF-N",
     "pit_warning": "published with the session, so it is point-in-time -- but it is the CASH "
                    "market's flow and says nothing about the offshore riyal or the sovereign "
                    "fund, which are the two largest Qatari balance sheets"},
    {"name": "Boursa Kuwait investor-type and nationality breakdown",
     "root": "https://www.boursakuwait.com.kw/en/market/statistical-reports",
     "fields": ("foreign_net", "kuwaiti_net", "institution_vs_individual", "sector_turnover"),
     "frequency": "daily and monthly", "snapshot": "each session", "publish_utc": "10:00",
     "lag_days": 0, "licence": "free, public", "available": True,
     "why": "Kuwait's retail base is unusually large and unusually leveraged through local "
            "margin lending, so the individual-versus-institution split is the closest thing "
            "the GCC has to a retail-positioning series",
     "pit_warning": "the monthly report revises the daily numbers; use the daily vintage"},
    {"name": "Muscat Stock Exchange monthly foreign investment statistics",
     "root": "https://msx.om/statistics", "fields": ("foreign_ownership_pct", "gcc_ownership_pct",
                                                     "arab_ownership_pct", "net_flow_omr"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "08:00", "lag_days": 10,
     "licence": "free, public", "available": True,
     "why": "the MSX publishes ownership by investor nationality band, which dates the periods "
            "in which GCC money rotated into and out of Oman around the rating path",
     "pit_warning": "monthly and ten days late; it conditions an era, never a week"},
    {"name": "Bahrain Bourse monthly trading and ownership statistics",
     "root": "https://bahrainbourse.com/market-statistics",
     "fields": ("foreign_ownership_pct", "gcc_vs_non_gcc", "turnover_by_sector"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "09:00", "lag_days": 12,
     "licence": "free, public", "available": True,
     "why": "the smallest tape in the GCC, and its foreign share is mostly GCC money, so a "
            "Bahraini outflow is a GULF-COHESION observable rather than an EM one",
     "pit_warning": "monthly, small and dominated by a handful of names"},
    {"name": "Central Bank of Kuwait weekly and monthly monetary statistics",
     "root": "https://www.cbk.gov.kw/en/statistics-and-publication/statistical-releases",
     "fields": ("kwd_usd_daily", "discount_rate", "public_deposits", "private_credit",
                "foreign_assets"),
     "frequency": "daily fixing, monthly statistics", "snapshot": "business day",
     "publish_utc": "06:00", "lag_days": 0, "licence": "free, public", "available": True,
     "why": "the daily dinar fixing is the estimation sample for `kwd_basket_beta`; the public "
            "deposit line is where a General Reserve Fund drawdown shows up before anyone "
            "announces one",
     "pit_warning": "the fixing is same-day; the balance-sheet lines are a month late"},
    {"name": "a CFTC or exchange-traded positioning series for QAR, KWD, OMR or BHD",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: none of the four currencies has a futures contract on any exchange "
            "the desk can read, and no COT line exists for any of them",
     "pit_warning": "DOES NOT EXIST. Gulf currency positioning is UNMEASURED and is never "
                    "proxied by the dollar-index COT: three of these four ARE the dollar by "
                    "construction, so a USD position is not a position in them, and the fourth "
                    "is a basket whose weights nobody outside the CBK knows"},
    {"name": "the Kuwait Investment Authority's holdings",
     "root": "https://www.kia.gov.kw", "fields": (), "frequency": "n/a", "snapshot": "",
     "publish_utc": "", "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT BY LAW. Kuwaiti Law 47 of 1982 makes the KIA's holdings a state "
            "secret; disclosing them is a criminal offence, and the fund does not publish an "
            "annual report, a size, or an asset allocation",
     "pit_warning": "DOES NOT EXIST AND WILL NOT. Every published KIA size is a third-party "
                    "ESTIMATE (SWF Institute, press). The pack uses the ESTIMATES as a "
                    "low-credibility observable and never as a series, and GULF-E is built on "
                    "the FLOW the law mandates -- 10% of revenue -- which is computable from "
                    "the published budget, rather than on the stock, which is not"},
)

# --------------------------------------------------------------------------- terminology
#: TWO LANGUAGES AND THE PACK MEANS BOTH. Arabic is the language of the decrees, the gazettes,
#: the four national presses and the retail ground; ENGLISH is the second official financial
#: language of the Gulf -- the central banks, the exchanges, the sovereign prospectuses, the
#: OPEC and DME documentation and half the sell-side research are published in it, often FIRST.
#: An Arabic-only crawl of this region misses the bond prospectus; an English-only crawl misses
#: the gazette, the sighting announcement and every retail forum. Both are required.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "GULF-A": ("حقل الشمال", "توسعة حقل الشمال", "الغاز الطبيعي المسال", "قطر للطاقة",
               "راس لفان", "الطاقة الإنتاجية", "مليون طن سنويا", "North Field expansion",
               "North Field East", "North Field South", "North Field West", "QatarEnergy",
               "Ras Laffan", "mtpa nameplate", "LNG train"),
    "GULF-B": ("اتفاقيات البيع طويلة الأجل", "التسعير المرتبط بالنفط", "مؤشر الغاز",
               "عقود طويلة الأجل", "وجهة الشحنة", "long-term SPA", "oil-indexed slope",
               "hub-indexed", "Brent slope", "destination flexibility", "term cargo",
               "sale and purchase agreement"),
    "GULF-C": ("الريال القطري", "سعر الصرف الثابت", "الحصار", "المقاطعة", "اتفاق العلا",
               "السوق الموازية", "النقاط الآجلة", "Qatari riyal peg", "the blockade",
               "Al-Ula declaration", "offshore riyal", "forward points", "correspondent banking"),
    "GULF-D": ("الدينار الكويتي", "سلة العملات", "بنك الكويت المركزي", "سعر الصرف اليومي",
               "سعر الخصم", "التعادل", "Kuwaiti dinar", "undisclosed basket", "CBK daily rate",
               "discount rate", "currency basket weights", "customer rate"),
    "GULF-E": ("صندوق الأجيال القادمة", "الهيئة العامة للاستثمار", "الاحتياطي العام",
               "قانون الدين العام", "مجلس الأمة", "الميزانية العامة", "تحويل 10%",
               "Future Generations Fund", "General Reserve Fund", "Kuwait Investment Authority",
               "public debt law", "National Assembly", "ten per cent transfer"),
    "GULF-F": ("أوبك بلس", "إعلان التعاون", "الحصص الإنتاجية", "خفض طوعي", "الالتزام بالحصص",
               "اجتماع اللجنة الوزارية", "OPEC+", "Declaration of Cooperation", "quota",
               "voluntary cut", "compliance", "JMMC", "non-OPEC participant"),
    "GULF-G": ("خام عمان", "بورصة دبي للطاقة", "العقود الآجلة", "سعر التسوية", "الخام الحامض",
               "هامش التكرير", "Oman crude futures", "DME Oman", "sour benchmark",
               "Brent-Dubai EFS", "settlement window", "Asian refining margin", "OSP"),
    "GULF-H": ("مضيق هرمز", "الدقم", "رأس مركز", "صحار", "ميناء الفحل", "خارج المضيق",
               "التخزين الاستراتيجي", "Strait of Hormuz", "Duqm", "Ras Markaz", "Sohar",
               "Mina al-Fahal", "chokepoint bypass", "strategic crude reserve"),
    "GULF-I": ("الدينار البحريني", "دعم دول الخليج", "الحزمة المالية", "العجز المالي",
               "التصنيف الائتماني", "ضريبة القيمة المضافة", "Bahraini dinar peg",
               "GCC support package", "fiscal balance programme", "credit rating",
               "value added tax", "external guarantee"),
    "GULF-J": ("المصارف الخارجية", "مركز مالي إقليمي", "سعر الفائدة بين البنوك",
               "الودائع الخليجية", "جسر الملك فهد", "مصرف البحرين المركزي", "offshore banking",
               "wholesale bank licence", "BHIBOR", "interbank spread", "King Fahd Causeway",
               "regional stress gauge"),
    "GULF-K": ("الربط بالدولار", "أسعار الصرف الثابتة", "النقاط الآجلة", "ضغط على الربط",
               "احتياطيات النقد الأجنبي", "مجلس التعاون الخليجي", "GCC dollar pegs",
               "peg stress", "forward points blowout", "reserve adequacy",
               "devaluation speculation", "one-year forward"),
    "GULF-L": ("إغلاق المضيق", "الملاحة البحرية", "التأمين البحري", "ناقلات النفط",
               "أمن الطاقة", "الممر المائي", "tanker insurance", "war risk premium",
               "freight rate", "transit volumes", "energy security", "maritime chokepoint"),
    "GULF-M": ("رمضان", "عيد الفطر", "عيد الأضحى", "موسم الحج", "استهلاك الذهب",
               "سوق الذهب", "استيراد الأغذية", "السيولة الموسمية", "Ramadan liquidity",
               "Eid demand", "Hajj season", "gold souk", "food import season",
               "Hijri seasonality"),
    "GULF-N": ("مؤشر مورغان ستانلي", "الترقية إلى الأسواق الناشئة", "إعادة التوازن",
               "تدفقات المؤشرات", "ملكية الأجانب", "بورصة قطر", "بورصة الكويت",
               "MSCI emerging markets upgrade", "FTSE Russell reclassification", "rebalance",
               "index inclusion flow", "foreign ownership limit", "passive flow"),
    "GULF-O": ("أسعار البيع الرسمية", "مؤسسة البترول الكويتية", "الخام الكويتي",
               "الفروق السعرية", "التسليم لآسيا", "official selling price", "KPC",
               "Kuwait Export Crude", "Asia differential", "monthly lifting", "term nomination"),
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

#: Arabic, including the presentation forms the web serves, so a test can assert this pack did
#: not quietly become an English glossary of an Arabic-speaking region.
_ARABIC_RANGES = ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF), (0xFB50, 0xFDFF),
                  (0xFE70, 0xFEFF))
#: The English working vocabulary the pack must ALSO carry: the prospectuses, the exchange rule
#: books, the OPEC and DME documentation and the sell-side notes are written in it, and an
#: Arabic-only crawl of the Gulf misses the half of the ground that prices the bonds.
ENGLISH_MARKERS: tuple[str, ...] = (
    "North Field expansion", "QatarEnergy", "undisclosed basket", "Future Generations Fund",
    "Declaration of Cooperation", "DME Oman", "Strait of Hormuz", "GCC support package",
    "BHIBOR", "forward points blowout", "official selling price", "Ramadan liquidity",
    "MSCI emerging markets upgrade", "Ras Markaz")


def has_arabic(text: str) -> bool:
    """True when the text contains at least one Arabic codepoint."""
    return any(any(lo <= ord(ch) <= hi for lo, hi in _ARABIC_RANGES) for ch in str(text))


def arabic_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return [t for terms in rows.values() for t in terms if has_arabic(t)]


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
                 machine_use_allowed: bool = True, notes: str = "") -> dict[str, Any]:
    """One class of source with the roots a crawler starts from and its three INDEPENDENT
    labels. `queries` carry the native script, never only a translation.
    `machine_use_allowed=True` registers ground whose terms forbid extraction: never scraped,
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


SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    # ---- official
    source_class(
        "gulf_qa_official", "Qatar: the central bank, the statistics authority, the Ministry of "
                            "Finance and the official gazette", layer="official",
        roots=("https://www.qcb.gov.qa", "https://www.psa.gov.qa",
               "https://www.mof.gov.qa", "https://www.almeezan.qa"),
        queries=("مصرف قطر المركزي", "تعميم مصرف قطر المركزي", "سعر الفائدة على الودائع",
                 "جهاز التخطيط والإحصاء", "النشرة الشهرية للتجارة الخارجية", "الميزانية العامة",
                 "الجريدة الرسمية", "قانون رقم", "احتياطيات النقد الأجنبي",
                 "Qatar Central Bank circular", "monthly trade bulletin", "state budget"),
        languages=("ar", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the PSA's monthly foreign-trade bulletin carries LNG export VALUE by destination, "
              "which is the only public read on what Qatar's contracts actually realise; "
              "Al Meezan is the state's legal portal where a decree becomes citable"),
    source_class(
        "gulf_kw_official", "Kuwait: the central bank, the Central Statistical Bureau, the "
                            "Ministry of Finance and Kuwait Al-Youm (the gazette)",
        layer="official",
        roots=("https://www.cbk.gov.kw", "https://www.csb.gov.kw", "https://www.mof.gov.kw",
               "https://www.kuwaitalyoum.gov.kw"),
        queries=("بنك الكويت المركزي", "سعر صرف الدينار الكويتي", "سلة العملات", "سعر الخصم",
                 "الإدارة المركزية للإحصاء", "الميزانية العامة للدولة", "الاحتياطي العام",
                 "صندوق الأجيال القادمة", "الكويت اليوم", "مرسوم بقانون",
                 "Kuwait daily exchange rate", "discount rate announcement"),
        languages=("ar", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE DAILY KWD RATE IS THE SAMPLE `kwd_basket_beta` NEEDS, and it is published on "
              "the CBK's own page every business day; Kuwait Al-Youm is where the debt law and "
              "the budget decree would appear if the National Assembly ever passed them"),
    source_class(
        "gulf_om_official", "Oman: the central bank, the NCSI, the Ministry of Energy and "
                            "Minerals and the Official Gazette", layer="official",
        roots=("https://cbo.gov.om", "https://www.ncsi.gov.om", "https://mem.gov.om",
               "https://qanoon.om"),
        queries=("البنك المركزي العماني", "أذون الخزانة", "الصكوك السيادية", "الريال العماني",
                 "المركز الوطني للإحصاء والمعلومات", "إنتاج النفط الخام", "صادرات النفط",
                 "وزارة الطاقة والمعادن", "الجريدة الرسمية", "مرسوم سلطاني",
                 "Oman crude production", "monthly statistical bulletin"),
        languages=("ar", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE MOST TRANSPARENT OIL PUBLISHER IN THE GULF: the NCSI prints monthly crude "
              "production, exports by destination AND the realised average price, which is what "
              "makes the DME marker's relationship to a real barrel measurable at all"),
    source_class(
        "gulf_bh_official", "Bahrain: the central bank, the open-data portal, the Ministry of "
                            "Finance and the Official Gazette", layer="official",
        roots=("https://www.cbb.gov.bh", "https://www.data.gov.bh", "https://www.mofne.gov.bh",
               "https://www.legalaffairs.gov.bh"),
        queries=("مصرف البحرين المركزي", "سعر الفائدة بين البنوك", "أذون الخزانة",
                 "الدينار البحريني", "الميزانية العامة", "برنامج التوازن المالي",
                 "الجريدة الرسمية", "مرسوم بقانون", "الدعم الخليجي",
                 "Bahrain interbank rate", "fiscal balance programme", "treasury bill auction"),
        languages=("ar", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the CBB publishes the interbank rate that is this pack's regional stress gauge; "
              "data.gov.bh is the only machine-readable open-data portal among the four and it "
              "carries the causeway and port series as well as the fiscal ones"),
    source_class(
        "gulf_multilateral", "GCC-Stat, the OPEC Secretariat, JODI and the IMF Article IV "
                             "country pages for all four states", layer="official",
        roots=("https://www.gccstat.org", "https://www.opec.org/opec_web/en/publications/338.htm",
               "https://www.jodidata.org", "https://www.imf.org/en/Countries/QAT",
               "https://www.imf.org/en/Countries/KWT", "https://www.imf.org/en/Countries/OMN",
               "https://www.imf.org/en/Countries/BHR"),
        queries=("المركز الإحصائي لدول مجلس التعاون", "إحصاءات الخليج", "منظمة أوبك",
                 "التقرير الشهري", "الحصص الإنتاجية", "إعلان التعاون",
                 "GCC statistical centre", "OPEC monthly oil market report",
                 "Article IV Qatar", "Article IV Kuwait", "Article IV Oman",
                 "Article IV Bahrain", "fiscal breakeven oil price"),
        languages=("ar", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="GCC-Stat is the ONLY publisher that harmonises the six members' definitions, "
              "which is what makes a cross-state control honest; the IMF's fiscal-breakeven "
              "estimate per country is the number that says how hard each state needs a price"),
    # ---- institutional
    source_class(
        "gulf_exchanges", "The four national exchanges and the Oman crude futures venue: QE, "
                          "Boursa Kuwait, MSX, Bahrain Bourse, DME/Gulf Mercantile Exchange",
        layer="institutional",
        roots=("https://www.qe.com.qa", "https://www.boursakuwait.com.kw", "https://msx.om",
               "https://bahrainbourse.com", "https://www.dubaimerc.com"),
        queries=("بورصة قطر", "التداول حسب الجنسية", "بورصة الكويت", "التقارير الإحصائية",
                 "بورصة مسقط", "الاستثمار الأجنبي", "بورصة البحرين", "بورصة دبي للطاقة",
                 "خام عمان الآجل", "سعر التسوية", "Qatar Exchange trading by nationality",
                 "Boursa Kuwait statistical report", "DME Oman settlement"),
        languages=("ar", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (exchange terms)",
        notes="the QE's trading-by-nationality page is a DAILY net foreign flow number for a "
              "market no CFD quotes; the DME is named as a FUTURES EXCHANGE behind a benchmark "
              "and no order book, depth or feed is taken from it"),
    source_class(
        "gulf_energy_soe", "The state energy companies as ISSUERS: QatarEnergy, Kuwait Petroleum "
                           "Corporation, OQ and Petroleum Development Oman, Bapco Energies, "
                           "Nakilat", layer="institutional",
        roots=("https://www.qatarenergy.qa", "https://www.kpc.com.kw", "https://oq.com",
               "https://www.pdo.co.om", "https://bapcoenergies.com"),
        queries=("قطر للطاقة", "توسعة حقل الشمال", "اتفاقية بيع وشراء", "مؤسسة البترول الكويتية",
                 "أسعار البيع الرسمية", "تنمية نفط عمان", "مصفاة الدقم", "بابكو",
                 "QatarEnergy SPA announcement", "North Field FID", "KPC official selling price",
                 "Duqm refinery", "Nakilat fleet"),
        languages=("ar", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public (issuer disclosure)",
        notes="these are BOND ISSUERS, so they disclose volumes, capacity and project timetables "
              "that a purely state-owned company would not; every one of them is an ACTOR in "
              "this pack and NEVER an instrument -- the two-lane order forbids hunting a name"),
    source_class(
        "gulf_sovereign_funds", "The four sovereign funds and what each of them does and does "
                                "not publish: QIA, KIA, Oman Investment Authority, Mumtalakat",
        layer="institutional",
        roots=("https://www.qia.qa", "https://www.kia.gov.kw", "https://www.oia.gov.om",
               "https://www.mumtalakat.bh"),
        queries=("جهاز قطر للاستثمار", "الهيئة العامة للاستثمار", "جهاز الاستثمار العماني",
                 "ممتلكات البحرين", "التقرير السنوي", "المحفظة الاستثمارية",
                 "Qatar Investment Authority", "Oman Investment Authority annual report",
                 "Mumtalakat audited accounts", "sovereign wealth fund disclosure"),
        languages=("ar", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public where published",
        notes="FOUR FUNDS, FOUR DISCLOSURE REGIMES, and the difference is the mechanism: the OIA "
              "publishes an annual report and Mumtalakat audited accounts, the QIA publishes "
              "almost nothing, and the KIA publishes NOTHING BY LAW (Law 47/1982). A Gulf "
              "'sovereign fund flow' claim that pools the four is pooling one measured series "
              "with one legally unmeasurable one"),
    source_class(
        "gulf_bank_research", "Openly published Gulf bank and broker research: QNB Economics "
                              "Weekly, NBK Economic Reports, Kamco Invest, Bank Muscat, SICO "
                              "Bahrain, Kuwait Financial Centre (Markaz)",
        layer="institutional",
        roots=("https://www.qnb.com/sites/qnb/qnbglobal/page/en/eneconomiccommentary.html",
               "https://www.nbk.com/kuwait/news-and-insights/economic-reports.html",
               "https://www.kamcoinvest.com/research", "https://www.markaz.com/research"),
        queries=("التقرير الاقتصادي الأسبوعي", "توقعات الاقتصاد الكويتي", "تقرير السوق",
                 "نظرة على أسواق الخليج", "QNB economic commentary", "NBK economic report",
                 "Markaz daily market report", "GCC markets monthly"),
        languages=("ar", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free notes; some behind registration",
        notes="NBK's and Markaz's weeklies are the only stated consensus in these markets and "
              "are kept as the EXPECTATION the pack measures a surprise AGAINST, never as a "
              "view the desk adopts"),
    # ---- academic
    source_class(
        "gulf_academic", "Gulf universities and regional research institutes: Qatar University, "
                         "the Kuwait Institute for Scientific Research, Sultan Qaboos "
                         "University, the University of Bahrain, the Gulf Research Center, the "
                         "Economic Research Forum, plus OpenAlex and CORE for the literature",
        layer="academic",
        roots=("https://www.qu.edu.qa/research", "https://www.kisr.edu.kw",
               "https://www.squ.edu.om/research", "https://erf.org.eg/publications/",
               "https://openalex.org", "https://core.ac.uk"),
        queries=("سياسة سعر الصرف الخليجية", "الاتحاد النقدي الخليجي", "الربط بالدولار",
                 "تنويع الاقتصاد", "صناديق الثروة السيادية", "الاقتصاد الريعي",
                 "GCC monetary union", "dollar peg optimality Gulf", "oil revenue volatility",
                 "sovereign wealth fund stabilisation", "Kuwait basket peg estimation"),
        languages=("ar", "en"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access / publisher terms",
        notes="THE KUWAIT BASKET HAS ITS OWN LITERATURE: several published papers estimate the "
              "undisclosed weights from the daily fixings, which is the mechanism source for "
              "GULF-D and `kwd_basket_beta` -- and every one of them is a hypothesis until the "
              "desk reproduces it on its own sample"),
    source_class(
        "gulf_energy_academic", "The energy-economics institutes that publish the LNG contract "
                                "and OPEC+ literature openly: the Oxford Institute for Energy "
                                "Studies, KAPSARC, Columbia CGEP, the Baker Institute",
        layer="academic",
        roots=("https://www.oxfordenergy.org/publications/", "https://www.kapsarc.org/research/",
               "https://www.energypolicy.columbia.edu/research/"),
        queries=("عقود الغاز طويلة الأجل", "التسعير المرتبط بالنفط", "أسواق الغاز المسال",
                 "LNG contract slope Brent", "hub indexation Asia LNG",
                 "OPEC+ compliance measurement", "Qatar LNG expansion market impact",
                 "Asian sour crude benchmark Oman"),
        languages=("en", "ar"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access",
        notes="OIES is where the Brent-slope-to-hub-indexation shift of GULF-B is documented "
              "with dated contract examples; it is a mechanism source and never a price series"),
    # ---- practitioner
    source_class(
        "gulf_practitioner_ar", "The Arabic market desk press: Argaam, Mubasher, Zawya Arabic, "
                                "Attaqa (energy), Alrroya, Al-Eqtisadiah Gulf pages",
        layer="practitioner",
        roots=("https://www.argaam.com", "https://www.mubasher.info", "https://www.zawya.com",
               "https://attaqa.net"),
        queries=("أرقام", "مباشر", "أسواق الخليج اليوم", "توصيات الأسهم", "أسعار البيع الرسمية",
                 "شحنات الغاز المسال", "اجتماع أوبك بلس", "حصة عمان الإنتاجية",
                 "الطاقة الإنتاجية لحقل الشمال", "سيولة السوق"),
        languages=("ar", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="Argaam and Mubasher carry the OSP, the SPA and the quota news hours before the "
              "official page updates, and Attaqa is the one Arabic outlet that reports the "
              "CONTRACT TERMS of a Qatari SPA rather than only its headline volume"),
    source_class(
        "gulf_lng_shipping_practitioner", "The LNG, crude and tanker practitioner press with "
                                          "free tiers: LNG Prime, Riviera, Splash247, "
                                          "TradeWinds headlines, gCaptain", layer="practitioner",
        roots=("https://lngprime.com", "https://www.rivieramm.com", "https://splash247.com"),
        queries=("Ras Laffan loading", "Qatar LNG cargo diverted", "Q-Max charter",
                 "Hormuz war risk premium", "Duqm crude storage", "Oman loading programme",
                 "ناقلات الغاز المسال", "شحنة غاز من راس لفان"),
        languages=("en", "ar"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms; free tier only",
        notes="the fastest public read on a Qatari cargo diversion or a war-risk premium step; "
              "the underlying freight ASSESSMENTS are licensed and are registered separately"),
    # ---- retail ecology
    source_class(
        "gulf_retail_forums", "Gulf retail communities: the Kuwaiti equity forums, Arabic "
                              "finance accounts on X and Telegram, r/Kuwait, r/Qatar, r/Oman "
                              "and r/Bahrain", layer="retail_ecology",
        roots=("https://www.reddit.com/r/Kuwait/", "https://www.reddit.com/r/qatar/",
               "https://www.reddit.com/r/Oman/", "https://www.reddit.com/r/Bahrain/",
               "https://www.q8yat.com"),
        queries=("منتدى الأسهم الكويتية", "توصيات اليوم", "سوق الكويت للأوراق المالية",
                 "شنو أشتري", "تداول الذهب", "الاستثمار في البورصة", "التمويل الشخصي",
                 "gold souk price today Kuwait", "best broker Qatar"),
        languages=("ar", "en"), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="KEPT AT LOW WEIGHT AND NEVER A SOURCE OF EDGE. Kuwait's retail base is unusually "
              "large and margin-financed, so the forum vocabulary dates the local leverage "
              "episodes; single-name tips belong to the event lane and are not hunted here"),
    source_class(
        "gulf_forex_sellers", "Arabic-language 'forex' signal sellers, prop-firm affiliates and "
                              "gold-trading channels targeting Gulf retail on Telegram, YouTube "
                              "and TikTok", layer="retail_ecology",
        roots=("https://www.youtube.com/results?search_query=تداول+الذهب+الخليج",
               "https://t.me/s/forexgulf"),
        queries=("فوركس الخليج", "تداول الذهب", "شركة وساطة مرخصة", "حساب تجريبي",
                 "توصيات مجانية", "prop firm Kuwait", "gold scalping Arabic"),
        languages=("ar", "en"), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="THREE OF THESE FOUR STATES LICENSE NO RETAIL MARGIN BROKERAGE AT ALL and it is "
              "advertised anyway, so this ground measures an unlicensed offshore retail base "
              "rather than a regulated flow; kept because the XAUUSD stop clusters it "
              "advertises around the Gulf morning are a real microstructure observable"),
    # ---- app ecosystem
    source_class(
        "gulf_payment_rails", "The payment and remittance rails: KNET (Kuwait), BENEFIT "
                              "(Bahrain), Qatar's Fawran instant payments and NAPS, Oman's "
                              "mobile payment clearing, and the exchange houses",
        layer="app_ecosystem",
        roots=("https://www.knet.com.kw", "https://www.benefit.bh",
               "https://www.qcb.gov.qa/en/paymentsystems", "https://cbo.gov.om/Pages/Payment.aspx"),
        queries=("كي نت", "بنفت", "فوران", "التحويلات المالية", "شركات الصرافة",
                 "المدفوعات الإلكترونية", "حوالة", "KNET transaction volumes",
                 "BENEFIT payment statistics", "Fawran instant payment", "remittance outflows"),
        languages=("ar", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free statistics; app stores public",
        notes="BENEFIT and KNET publish card and transfer volumes, which is a near-real-time "
              "domestic demand proxy; the exchange houses' outbound corridors are the physical "
              "counterpart of the month-end remittance flow into USDINR"),
    source_class(
        "gulf_broker_apps", "The exchanges' and local brokers' retail platforms and their "
                            "published usage: QE's app, Boursa Kuwait's Tadawul app, the MSX "
                            "and Bahrain Bourse investor portals, the Gulf bank trading apps",
        layer="app_ecosystem",
        roots=("https://www.qe.com.qa/investor-tools", "https://www.boursakuwait.com.kw",
               "https://bahrainbourse.com/investor-services"),
        queries=("تطبيق التداول", "محفظة المستثمر", "رقم المستثمر الوطني", "فتح حساب تداول",
                 "investor number Qatar", "Boursa Kuwait app", "online trading account Oman"),
        languages=("ar", "en"), access_label="PUBLIC", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="app-store and exchange terms",
        notes="THE THIN LAYER IN THIS PACK, and it is declared thin rather than padded: none of "
              "the four publishes app-level retail activity, so this layer carries the ACCOUNT "
              "and investor-number statistics and nothing that pretends to be an order flow"),
    # ---- media
    source_class(
        "gulf_press_ar", "The four national presses in Arabic: Al-Qabas and Al-Rai (Kuwait), "
                         "Al-Sharq and Al-Raya (Qatar), Oman Daily (عمان) and Al-Watan (Oman), "
                         "Akhbar Al-Khaleej and Al-Ayam (Bahrain)", layer="media",
        roots=("https://www.alqabas.com", "https://al-sharq.com", "https://www.omandaily.om",
               "https://www.akhbar-alkhaleej.com"),
        queries=("القبس", "أخبار الخليج", "جريدة عمان", "الشرق", "الميزانية العامة",
                 "سعر النفط", "قرار مجلس الوزراء", "العيد الوطني", "رؤية الهلال",
                 "دعم الوقود", "أسعار المواد الغذائية"),
        languages=("ar",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="Al-Qabas is the outlet that reports the KUWAITI PARLIAMENTARY politics of the "
              "debt law -- the single most important unpriced fact in GULF-E -- and no "
              "English-language source covers it at the same depth or on the same day"),
    source_class(
        "gulf_wire_broadcast", "The four state wires and the regional business broadcasters: QNA, "
                               "KUNA, ONA and BNA, plus Al Jazeera business and Asharq Business",
        layer="media",
        roots=("https://www.qna.org.qa", "https://www.kuna.net.kw", "https://omannews.gov.om",
               "https://www.bna.bh"),
        queries=("وكالة الأنباء القطرية", "وكالة الأنباء الكويتية", "وكالة الأنباء العمانية",
                 "وكالة أنباء البحرين", "بيان رسمي", "مرسوم أميري", "مرسوم سلطاني",
                 "اجتماع مجلس الوزراء", "official statement", "amiri decree"),
        languages=("ar", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="NARRATIVE_FEATURE", licence="free, public (wire terms)",
        notes="THE WIRE IS THE TIMESTAMP. A Gulf decree, a sighting announcement, a National Day "
              "closure and a central bank circular all appear on the state wire with a MINUTE "
              "before the institution's own page updates, and that minute is what an event "
              "study needs"),
    source_class(
        "gulf_licensed_assessments", "Licensed price reporting and freight: Platts and Argus for "
                                     "Dubai/Oman and for LNG, ICIS, Clarksons and the Baltic "
                                     "Exchange for tanker rates, plus the terminals",
        layer="media",
        roots=("https://www.spglobal.com/commodityinsights", "https://www.argusmedia.com",
               "https://www.balticexchange.com"),
        queries=("Dubai Oman assessment window", "Brent Dubai EFS", "JKM LNG assessment",
                 "VLCC AG-East rate", "war risk premium Gulf"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="subscription; terms forbid machine extraction",
        machine_use_allowed=True,
        notes="REGISTERED, NEVER SCRAPED. The Dubai/Oman assessment, the JKM LNG marker and the "
              "AG-East tanker rate are the three prices this pack would most like and cannot "
              "have, so GULF-G and GULF-L are measured on the EXCHANGE-TRADED legs and the "
              "physical loadings instead -- the absence is named, not worked around"),
    # ---- archive
    source_class(
        "gulf_gazettes_archive", "The four official gazettes in full run, the central bank "
                                 "annual reports and the exchange yearbooks", layer="archive",
        roots=("https://www.almeezan.qa/Gazette.aspx", "https://www.kuwaitalyoum.gov.kw",
               "https://qanoon.om/p/gazette/", "https://www.legalaffairs.gov.bh/Gazette.aspx"),
        queries=("الجريدة الرسمية أرشيف", "الكويت اليوم أعداد سابقة", "مرسوم سلطاني رقم",
                 "مرسوم أميري رقم", "قانون رقم لسنة", "التقرير السنوي للبنك المركزي",
                 "الكتاب الإحصائي السنوي", "official gazette archive",
                 "central bank annual report"),
        languages=("ar", "en"), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE GAZETTE IS WHERE A GULF DECISION BECOMES CITABLE, and it is the only place a "
              "peg parameter, a budget law or a fund-transfer rule can be dated to a document "
              "rather than to a press report; Kuwait Al-Youm is the archive that holds the "
              "Future Generations Fund law and every amendment to it"),
    source_class(
        "gulf_wayback", "web.archive.org snapshots of the pages that OVERWRITE IN PLACE: the CBK "
                        "daily rate table, the QE trading-by-nationality page, the MSX statistics "
                        "page and the CBB rate page", layer="archive",
        roots=("https://web.archive.org/web/*/cbk.gov.kw*",
               "https://web.archive.org/web/*/qe.com.qa*",
               "https://web.archive.org/web/*/msx.om*"),
        queries=("CBK daily exchange rate archive", "Qatar Exchange nationality archive",
                 "MSX statistics archive", "أرشيف سعر صرف الدينار"),
        languages=("ar", "en"), access_label="PUBLIC_ARCHIVE", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="Internet Archive terms",
        notes="THE GULF OFFICIAL WEB SHOWS TODAY AND KEEPS NO HISTORY. The CBK's daily dinar "
              "rate -- the single series `kwd_basket_beta` is built on -- is published as a "
              "CURRENT table, so without this layer the estimation sample exists only as far "
              "back as somebody's crawl, and a cell compiled on an un-archived month is "
              "UNMEASURED rather than assumed"),
    # ---- physical economy
    source_class(
        "gulf_ports_loadings", "The loading points themselves: Ras Laffan and Mesaieed (Mwani "
                               "Qatar), the Kuwait Ports Authority, Duqm, Sohar and Salalah in "
                               "Oman, and Khalifa Bin Salman Port in Bahrain",
        layer="physical_economy",
        roots=("https://www.mwani.com.qa", "https://www.kpa.gov.kw", "https://www.portduqm.com",
               "https://www.soharportandfreezone.com", "https://www.salalahport.com.om"),
        queries=("ميناء راس لفان", "ميناء الدقم", "ميناء صحار", "ميناء صلالة",
                 "المؤسسة العامة للموانئ", "حركة الشحن", "عدد السفن", "الحمولة",
                 "Ras Laffan berth", "Duqm port throughput", "Sohar volumes",
                 "port call statistics"),
        languages=("ar", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="RAS LAFFAN IS INSIDE THE STRAIT AND DUQM IS NOT, which is the whole of GULF-H: "
              "the two port ground truths are the control and the treatment of any Hormuz claim, "
              "and both publish throughput"),
    source_class(
        "gulf_energy_physical", "The physical energy series: JODI-Oil and JODI-Gas for all four "
                                "states, the EIA's Hormuz transit estimates, the IEA monthly "
                                "balances and Oman's own NCSI production print",
        layer="physical_economy",
        roots=("https://www.jodidata.org/oil/", "https://www.jodidata.org/gas/",
               "https://www.eia.gov/international/analysis/special-topics/"
               "World_Oil_Transit_Chokepoints", "https://www.ncsi.gov.om"),
        queries=("إنتاج النفط الخام", "صادرات الغاز المسال", "الاستهلاك المحلي",
                 "JODI oil production Kuwait", "JODI gas exports Qatar",
                 "Hormuz transit volumes", "Oman monthly production", "crude stocks"),
        languages=("en", "ar"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public (JODI and US government work)",
        notes="JODI IS SELF-REPORTED and its Gulf rows are revised heavily, which is a property "
              "of the series and not a reason to drop it: the REVISION is itself an observable, "
              "and Oman's NCSI print is the independent read that dates the revisions"),
    source_class(
        "gulf_causeway_traffic", "The King Fahd Causeway Authority traffic statistics and the "
                                 "Bahrain open-data portal's transport series",
        layer="physical_economy",
        roots=("https://www.kfca.com.sa", "https://www.data.gov.bh"),
        queries=("جسر الملك فهد", "حركة المرور", "عدد المسافرين", "عدد المركبات",
                 "King Fahd Causeway traffic", "monthly crossings", "Bahrain visitor arrivals"),
        languages=("ar", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="A PHYSICAL OBSERVABLE FOR AN ECONOMY WITH ALMOST NO OTHERS. Bahrain's weekend "
              "economy is Saudi visitors arriving by road, so the causeway count is a real, "
              "counted, high-frequency demand series -- and its 2020 collapse and reopening "
              "date the only genuine natural experiment this small state offers"),
    # ---- source graph
    source_class(
        "gulf_source_graph", "Who cites whom across the Gulf: the state wire -> Argaam, Mubasher "
                             "and Zawya -> the retail forums; the gazette -> the central bank "
                             "circular -> the bank research note; the OPEC secretariat -> the "
                             "agency survey -> the ministers' remarks", layer="source_graph",
        roots=("https://www.qna.org.qa", "https://www.argaam.com", "https://www.zawya.com"),
        queries=("وفقا لمصادر", "حسب مصادر مطلعة", "نقلا عن وكالة الأنباء", "قالت مصادر",
                 "أفادت وكالة", "according to sources familiar", "citing the official gazette",
                 "as reported by the state news agency"),
        languages=("ar", "en"), access_label="PUBLIC", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="derived from the public sources above",
        notes="'حسب مصادر مطلعة' is the marker of the unattributed Gulf leak, and in this region "
              "it precedes an OSP change, a quota decision or a fund transfer by a day or two; "
              "the graph is how a leak is told from a repost, and it is the only way to date a "
              "GULF-O or GULF-F decision before the official page carries it"),
)

#: DECLARED EMPTY, AND THAT IS A MEASUREMENT TOO: all ten layers carry at least one real source
#: for these four states. The honest refusals in this pack are not whole layers -- they are the
#: named sub-grounds in NO_LAWFUL_GROUND below, where a specific series does not exist or may not
#: be machine-read.
LAYER_ABSENCES: dict[str, str] = {}

#: WHERE THE GROUND GENUINELY DOES NOT EXIST, NAMED. Not a layer absence -- a SERIES absence, and
#: each one bounds a domain rather than blocking it. This is the measured refusal (L1.28a): a
#: study that needs one of these rows answers UNMEASURED and says which one.
NO_LAWFUL_GROUND: tuple[dict[str, str], ...] = (
    {"what": "the Kuwait Investment Authority's size, holdings or allocation",
     "why": "Law 47 of 1982 makes KIA disclosure a criminal offence; the fund publishes no "
            "annual report, no size and no allocation, and every circulating number is a "
            "third-party estimate",
     "consequence": "GULF-E is built on the statutory FLOW (10% of revenue, computable from the "
                    "published budget) and never on the stock"},
    {"what": "the weights of the Kuwaiti dinar's currency basket",
     "why": "the CBK has never published them and has said it will not",
     "consequence": "the USD beta is ESTIMATED from the published daily fixings by "
                    "`kwd_basket_beta` and carried with its standard error, never asserted"},
    {"what": "a COT or exchange positioning series for QAR, KWD, OMR or BHD",
     "why": "no futures contract exists for any of the four on any exchange the desk can read",
     "consequence": "Gulf currency positioning is UNMEASURED by name; the dollar-index COT is "
                    "NOT a proxy, because three of the four ARE the dollar by construction"},
    {"what": "the Platts Dubai/Oman assessment, the JKM LNG marker and the Baltic AG-East rate",
     "why": "all three are licensed products whose terms forbid machine extraction; they are "
            "registered with machine_use_allowed=false and never fetched",
     "consequence": "GULF-G and GULF-L are measured on the exchange-traded crude legs and on "
                    "counted physical loadings instead"},
    {"what": "the slope of any QatarEnergy long-term sale and purchase agreement",
     "why": "the contracts are bilateral and the slope is disclosed only in fragments, through "
            "counterparty filings and press reporting",
     "consequence": "GULF-B conditions on the ERA of the pricing regime -- oil-indexed, mixed, "
                    "hub-indexed -- rather than on a slope series that does not exist"},
    {"what": "an intraday tape for the QE, Boursa Kuwait, MSX or Bahrain Bourse",
     "why": "none of the four publishes a public intraday tape, and no CFD is quoted on any of "
            "their indices",
     "consequence": "every Gulf equity mechanism in this pack terminates in the risk complex, "
                    "the dollar or the energy legs, and the local index is an OBSERVABLE"},
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
            "no_lawful_ground": [row["what"] for row in NO_LAWFUL_GROUND],
            "rule": "ten layers, each carrying a source or named ABSENT with a reason; fringe "
                    "and contradicted PUBLIC material is kept as a low-weight evidence object "
                    "and never dropped; a page whose terms forbid machine extraction is "
                    "registered machine_use_allowed=false, never scraped and never omitted; a "
                    "series that does not lawfully exist is named in NO_LAWFUL_GROUND with the "
                    "domain it bounds"}


#: NATIVE QUERY TERRITORIES: what the deep-forest miner actually types, per layer, in Arabic
#: first and English second. English is not a translation convenience here -- it is the SECOND
#: OFFICIAL FINANCIAL LANGUAGE of the Gulf, and the prospectuses, the exchange rule books and
#: the OPEC and DME documentation are published in it, frequently before the Arabic.
QUERY_TERRITORIES: dict[str, tuple[str, ...]] = {
    "official": ("سعر صرف الدينار الكويتي اليوم", "تعميم مصرف قطر المركزي",
                 "إنتاج النفط الخام العماني الشهري", "أذون الخزانة البحرينية",
                 "الميزانية العامة للدولة الكويتية", "الجريدة الرسمية مرسوم",
                 "Kuwait daily exchange rate CBK", "Oman monthly crude production NCSI",
                 "Bahrain treasury bill auction result"),
    "institutional": ("بورصة قطر التداول حسب الجنسية", "بورصة الكويت التقرير الإحصائي",
                      "قطر للطاقة اتفاقية بيع وشراء", "مؤسسة البترول الكويتية أسعار البيع",
                      "جهاز الاستثمار العماني التقرير السنوي",
                      "Qatar Exchange trading by nationality", "QatarEnergy SPA signed",
                      "DME Oman futures settlement price"),
    "academic": ("تقدير أوزان سلة الدينار الكويتي", "الربط بالدولار في دول الخليج",
                 "الاتحاد النقدي الخليجي", "أثر تقلبات النفط على الاقتصاد الخليجي",
                 "Kuwait currency basket weight estimation", "GCC dollar peg sustainability",
                 "LNG contract indexation Brent slope", "Oman sour crude benchmark literature"),
    "practitioner": ("أرقام أسواق الخليج", "مباشر بورصة الكويت", "الطاقة شحنات الغاز المسال",
                     "توقعات اجتماع أوبك بلس", "تحليل السوق القطري",
                     "Argaam GCC market wrap", "LNG Prime Ras Laffan", "Markaz daily report"),
    "retail_ecology": ("منتدى الأسهم الكويتية توصيات", "أسعار الذهب في السوق اليوم",
                       "تداول الذهب للمبتدئين", "أفضل شركة وساطة في قطر",
                       "r/Kuwait investing", "gold souk price Bahrain", "forex broker Oman"),
    "app_ecosystem": ("كي نت إحصائيات العمليات", "بنفت حجم المدفوعات", "فوران التحويل الفوري",
                      "تطبيق تداول بورصة الكويت", "شركات الصرافة تحويل",
                      "KNET transaction statistics", "BENEFIT payment volumes",
                      "Fawran instant payment Qatar"),
    "media": ("القبس قانون الدين العام", "أخبار الخليج الدعم الخليجي", "جريدة عمان الميزانية",
              "الشرق اليوم الوطني", "وكالة الأنباء الكويتية بيان",
              "Kuwait public debt law parliament", "Bahrain GCC support package",
              "Oman budget statement"),
    "archive": ("الجريدة الرسمية أعداد سابقة", "الكويت اليوم أرشيف", "مرسوم سلطاني رقم أرشيف",
                "التقرير السنوي لبنك الكويت المركزي", "الكتاب الإحصائي السنوي",
                "official gazette archive Qatar", "CBK daily rate wayback",
                "Qatar Exchange nationality archive"),
    "physical_economy": ("ميناء راس لفان حركة", "ميناء الدقم حركة الشحن", "جسر الملك فهد حركة",
                         "صادرات النفط العماني حسب الوجهة", "مضيق هرمز الملاحة",
                         "Ras Laffan loading programme", "Duqm port throughput",
                         "Hormuz transit volumes EIA", "JODI Kuwait crude exports"),
    "source_graph": ("حسب مصادر مطلعة", "نقلا عن وكالة الأنباء", "وفقا لمصادر في القطاع",
                     "أفادت مصادر مطلعة على المفاوضات", "citing sources familiar with the matter",
                     "as reported by the state news agency", "according to the official gazette"),
}

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "CBK daily KWD/USD customer rate (the undisclosed-basket fixing)",
     "source": "Central Bank of Kuwait", "coverage": "2003 onward, every business day",
     "frequency": "daily (Sunday-Thursday)", "publication_lag_days": 0.0,
     "revisions": "never revised", "licence": "free, public", "history_from": "2003-01",
     "pit_feasible": True, "assets": ("USDX", "EURUSD", "USDJPY"),
     "mechanism_families": ("fixing", "basket_estimation"),
     "how_to_fetch": "cbk.gov.kw exchange-rates page; the table SHOWS TODAY and keeps no "
                     "history, so the vintage is a daily crawl or the Wayback snapshot -- this "
                     "is the estimation sample for `kwd_basket_beta`"},
    {"name": "Qatar Exchange trading by nationality and investor type",
     "source": "Qatar Stock Exchange", "coverage": "2012 onward, every session",
     "frequency": "daily", "publication_lag_days": 0.0, "revisions": "rarely",
     "licence": "free, public", "history_from": "2012-01", "pit_feasible": True,
     "assets": ("US500", "USDX", "UK100"),
     "mechanism_families": ("institutional_flow", "positioning"),
     "how_to_fetch": "qe.com.qa trading-by-nationality; published with the session close, so a "
                     "daily crawl at 11:00 UTC captures the vintage"},
    {"name": "North Field capacity schedule and QatarEnergy project milestones",
     "source": "QatarEnergy announcements and the state wire",
     "coverage": "2005 moratorium, 2017 lift, 2019-2024 capacity steps to 142 mtpa",
     "frequency": "irregular, dated", "publication_lag_days": 0.0,
     "revisions": "the SCHEDULE slips and the slip is the event", "licence": "free, public",
     "history_from": "2005-01", "pit_feasible": True,
     "assets": ("XNGUSD", "XBRUSD", "USDJPY"),
     "mechanism_families": ("supply_schedule", "event_reaction"),
     "how_to_fetch": "qatarenergy.qa media releases plus QNA; `north_field_capacity(year)` is "
                     "the pack's own resolved form of the same table"},
    {"name": "Kuwaiti and Qatari monthly official selling prices to Asia and the West",
     "source": "KPC and QatarEnergy monthly OSP circulars, carried by Argaam and the wires",
     "coverage": "2010 onward", "frequency": "monthly", "publication_lag_days": 0.0,
     "revisions": "never", "licence": "free where reported; the circular itself is to term "
                                      "customers",
     "history_from": "2010-01", "pit_feasible": True, "assets": ("XBRUSD", "XTIUSD", "USDINR"),
     "mechanism_families": ("administered_price", "event_reaction"),
     "how_to_fetch": "kpc.com.kw and the Argaam/Reuters report in the first week of the month; "
                     "the differential is quoted against the Oman/Dubai average for Asia"},
    {"name": "DME / Gulf Mercantile Exchange Oman crude futures settlement series",
     "source": "Dubai Mercantile Exchange", "coverage": "2007-06 launch onward",
     "frequency": "daily settlement", "publication_lag_days": 0.0,
     "revisions": "never", "licence": "free settlement summary; the full curve is licensed",
     "history_from": "2007-06", "pit_feasible": True, "assets": ("XBRUSD", "XTIUSD", "JPN225"),
     "mechanism_families": ("benchmark", "spread"),
     "how_to_fetch": "dubaimerc.com daily settlement summary; the marker window closes 16:30 "
                     "Singapore (08:30 UTC) and the settlement is the Asian sour reference"},
    {"name": "NCSI Oman monthly crude production, exports by destination and realised price",
     "source": "National Centre for Statistics and Information, Oman",
     "coverage": "2010 onward", "frequency": "monthly", "publication_lag_days": 30.0,
     "revisions": "revised once, usually in the following bulletin", "licence": "free, public",
     "history_from": "2010-01", "pit_feasible": True, "assets": ("XBRUSD", "XTIUSD"),
     "mechanism_families": ("physical_flow", "quota_compliance"),
     "how_to_fetch": "ncsi.gov.om monthly statistical bulletin; the only Gulf series that prints "
                     "production AND realised price, which is what makes DoC compliance "
                     "measurable for a non-OPEC member"},
    {"name": "OPEC Monthly Oil Market Report production table (secondary sources)",
     "source": "OPEC Secretariat", "coverage": "2000 onward", "frequency": "monthly",
     "publication_lag_days": 12.0, "revisions": "revised in later editions",
     "licence": "free, public", "history_from": "2000-01", "pit_feasible": True,
     "assets": ("XBRUSD", "XTIUSD"),
     "mechanism_families": ("quota_compliance", "release_surprise"),
     "how_to_fetch": "opec.org MOMR; MEMBERSHIP CHANGED UNDER THE NAME -- Qatar left OPEC on "
                     "2019-01-01 and Oman has never been a member, so the DoC tables and the "
                     "OPEC tables are two different universes and must not be pooled"},
    {"name": "JODI-Oil and JODI-Gas submissions for Qatar, Kuwait, Oman and Bahrain",
     "source": "Joint Organisations Data Initiative", "coverage": "2002 onward",
     "frequency": "monthly", "publication_lag_days": 60.0,
     "revisions": "heavily revised; the REVISION is itself an observable",
     "licence": "free, public", "history_from": "2002-01", "pit_feasible": True,
     "assets": ("XBRUSD", "XNGUSD"),
     "mechanism_families": ("physical_flow", "revision"),
     "how_to_fetch": "jodidata.org world database download; self-reported, so read against the "
                     "NCSI print for Oman and against loadings for Qatar"},
    {"name": "Qatar PSA monthly foreign trade bulletin (LNG export value by destination)",
     "source": "Planning and Statistics Authority, Qatar", "coverage": "2014 onward",
     "frequency": "monthly", "publication_lag_days": 35.0, "revisions": "minor",
     "licence": "free, public", "history_from": "2014-01", "pit_feasible": True,
     "assets": ("XNGUSD", "XBRUSD", "USDJPY"),
     "mechanism_families": ("realised_price", "trade_cycle"),
     "how_to_fetch": "psa.gov.qa foreign trade statistics; VALUE divided by VOLUME to Japan, "
                     "Korea and India is the only public estimate of the realised contract "
                     "price GULF-B is about"},
    {"name": "Central Bank of Bahrain interbank rate (BHIBOR) and treasury-bill cut-offs",
     "source": "Central Bank of Bahrain", "coverage": "2008 onward",
     "frequency": "daily fixing, weekly auction", "publication_lag_days": 0.0,
     "revisions": "never", "licence": "free, public", "history_from": "2008-01",
     "pit_feasible": True, "assets": ("UST05Y", "UST10Y", "USDX"),
     "mechanism_families": ("funding_stress", "carry_funding"),
     "how_to_fetch": "cbb.gov.bh rates and auction results; the BHIBOR-minus-SOFR spread is the "
                     "series, and it is the region's cheapest public stress gauge"},
    {"name": "Central Bank of Oman treasury-bill and sukuk auction results",
     "source": "Central Bank of Oman", "coverage": "2015 onward", "frequency": "weekly",
     "publication_lag_days": 0.0, "revisions": "never", "licence": "free, public",
     "history_from": "2015-01", "pit_feasible": True, "assets": ("UST05Y", "USDX"),
     "mechanism_families": ("funding_stress", "carry_funding"),
     "how_to_fetch": "cbo.gov.om auction announcements; the cut-off through 2020-2021 is the "
                     "local read on the rating path that the sovereign spread confirms"},
    {"name": "Kuwaiti state budget, revenue and the statutory Future Generations Fund transfer",
     "source": "Kuwait Ministry of Finance and the Central Statistical Bureau",
     "coverage": "fiscal years from 2010/11", "frequency": "annual with monthly execution",
     "publication_lag_days": 60.0, "revisions": "revised at the final account",
     "licence": "free, public", "history_from": "2010-04", "pit_feasible": True,
     "assets": ("USDX", "US500", "UST10Y"),
     "mechanism_families": ("fiscal_flow", "forced_seller"),
     "how_to_fetch": "mof.gov.kw budget statements; the 10%-of-revenue transfer is COMPUTABLE "
                     "from the published revenue line, which is how GULF-E is measured without "
                     "the KIA's own numbers"},
    {"name": "GCC-Stat harmonised statistics for the six member states",
     "source": "GCC Statistical Centre", "coverage": "2010 onward",
     "frequency": "quarterly and annual", "publication_lag_days": 90.0,
     "revisions": "revised", "licence": "free, public", "history_from": "2010-01",
     "pit_feasible": False, "assets": ("USDX", "US500"),
     "mechanism_families": ("cross_state_control",),
     "how_to_fetch": "gccstat.org data portal; NOT point-in-time -- it is the CONTROL that makes "
                     "a Qatar-versus-Oman comparison honest, and it conditions an era, never a "
                     "week"},
    {"name": "The four exchanges' daily index levels, turnover and foreign-share statistics",
     "source": "QE, Boursa Kuwait, MSX, Bahrain Bourse",
     "coverage": "2010 onward (QE from 2002)", "frequency": "daily to monthly",
     "publication_lag_days": 0.0, "revisions": "rarely", "licence": "free, public",
     "history_from": "2010-01", "pit_feasible": True, "assets": ("US500", "UK100", "USDX"),
     "mechanism_families": ("index_flow", "equity_mechanics"),
     "how_to_fetch": "each exchange's market-statistics page; no CFD is quoted on any of the "
                     "four indices, so these are OBSERVABLES that condition a dollar or risk leg"},
    {"name": "MSCI and FTSE Russell reclassification decisions and effective dates for the GCC",
     "source": "MSCI and FTSE Russell index announcements", "coverage": "2013 onward",
     "frequency": "irregular, dated", "publication_lag_days": 0.0, "revisions": "the EFFECTIVE "
                                                                                "DATE can move",
     "licence": "free announcements; the index data is licensed",
     "history_from": "2013-06", "pit_feasible": True, "assets": ("US500", "UK100", "USDX"),
     "mechanism_families": ("index_flow", "event_reaction"),
     "how_to_fetch": "the MSCI and FTSE market-classification announcements; Kuwait's 2020 "
                     "upgrade was DELAYED from May to November by COVID, and the delay is the "
                     "cleanest placebo an inclusion study on this region can have"},
    {"name": "King Fahd Causeway monthly traffic (vehicles and passengers)",
     "source": "King Fahd Causeway Authority and data.gov.bh", "coverage": "2015 onward",
     "frequency": "monthly", "publication_lag_days": 20.0, "revisions": "never",
     "licence": "free, public", "history_from": "2015-01", "pit_feasible": True,
     "assets": ("USDX", "XAUUSD"),
     "mechanism_families": ("physical_flow", "demand_nowcast"),
     "how_to_fetch": "kfca.com.sa statistics and the Bahrain open-data portal; the 2020 closure "
                     "and reopening are the only clean natural experiment in Bahraini demand"},
    {"name": "KNET and BENEFIT card and instant-payment transaction volumes",
     "source": "KNET (Kuwait) and BENEFIT (Bahrain)", "coverage": "2016 onward",
     "frequency": "monthly", "publication_lag_days": 25.0, "revisions": "never",
     "licence": "free statistics", "history_from": "2016-01", "pit_feasible": True,
     "assets": ("USDX", "XAUUSD", "SUGAR"),
     "mechanism_families": ("demand_nowcast", "seasonality"),
     "how_to_fetch": "knet.com.kw and benefit.bh published statistics; the Ramadan and Eid steps "
                     "in these series are the household-demand leg of GULF-M"},
    {"name": "Gulf port throughput and loading statistics (Ras Laffan, Duqm, Sohar, Salalah)",
     "source": "Mwani Qatar, Kuwait Ports Authority, Port of Duqm, Sohar, Salalah",
     "coverage": "2016 onward", "frequency": "monthly to quarterly",
     "publication_lag_days": 45.0, "revisions": "minor", "licence": "free, public",
     "history_from": "2016-01", "pit_feasible": True, "assets": ("XNGUSD", "XBRUSD"),
     "mechanism_families": ("physical_flow", "chokepoint"),
     "how_to_fetch": "each port authority's statistics page; the INSIDE-versus-OUTSIDE-Hormuz "
                     "split (`hormuz_bypass_share`) is what turns these counts into the control "
                     "GULF-H needs"},
    {"name": "The four states' USD sovereign issuance calendar and outstanding stock",
     "source": "the finance ministries' investor pages and the prospectuses",
     "coverage": "2016 onward", "frequency": "irregular, dated",
     "publication_lag_days": 0.0, "revisions": "never", "licence": "free, public",
     "history_from": "2016-01", "pit_feasible": True, "assets": ("UST05Y", "UST10Y", "USDX"),
     "mechanism_families": ("fiscal_flow", "issuance"),
     "how_to_fetch": "mof.gov.qa, mofne.gov.bh, cbo.gov.om investor relations; a Gulf issuance "
                     "window is a DATED dollar-demand event and Bahrain's and Oman's are the "
                     "two that have ever been in doubt"},
    {"name": "EIA world oil transit chokepoint estimates for the Strait of Hormuz",
     "source": "US Energy Information Administration", "coverage": "2011 onward",
     "frequency": "annual with occasional updates", "publication_lag_days": 180.0,
     "revisions": "revised", "licence": "public domain (US government work)",
     "history_from": "2011-01", "pit_feasible": False, "assets": ("XBRUSD", "XTIUSD", "XNGUSD"),
     "mechanism_families": ("chokepoint", "supply_risk"),
     "how_to_fetch": "eia.gov world oil transit chokepoints; ANNUAL and slow, so it sizes the "
                     "exposure and never times an event -- the timing comes from the loadings"},
)

# --------------------------------------------------------------------------- actors
#: TWENTY-FOUR ACTORS, ABOUT FIVE PER STATE PLUS THE SHARED ONES. `jurisdiction` is this pack's
#: own field and is folded into the framework row's notes rather than dropped, because a Gulf
#: actor that is not attributed to a state reads as "the Gulf" and the whole point of this pack
#: is that the four are not one thing.
ACTORS: tuple[dict[str, Any], ...] = (
    # ------------------------------------------------------------------ Qatar
    {"name": "QatarEnergy as the operator of the North Field expansion",
     "jurisdiction": "qa",
     "holds": "the world's largest non-associated gas field, a 77 mtpa LNG plateau, the announced "
              "trains that take it to 110, 126 and 142 mtpa, and the Ras Laffan loading complex",
     "forced_to": ("build to a PUBLISHED capacity schedule with dated trains, because the EPC "
                   "contracts, the partner equity and the shipbuilding orders are all signed "
                   "against it",
                   "sell most of the volume under long-term SPAs rather than into the spot "
                   "market, because the expansion is financed against contracted offtake",
                   "load every cargo through the Strait of Hormuz -- there is no bypass"),
     "when": "project milestones are announced through QNA and the company's own releases in "
             "Doha business hours (about 07:00-13:00 UTC); loading programmes are set into the "
             "month boundary",
     "information": ("the field's own reservoir and train commissioning schedule",
                     "the full term-contract book and its price formulas",
                     "the monthly loading programme before any tracker sees the ships",
                     "the buyers' nomination behaviour under the flexibility clauses"),
     "constraints": ("an EPC and commissioning timetable that slips and cannot be hurried",
                     "a state fiscal plan built on the expansion arriving",
                     "the strait, which no amount of capacity removes",
                     "buyers who now have alternatives -- US Gulf Coast supply competes for the "
                     "same 2026-2030 window"),
     "instruments": ("XNGUSD", "XBRUSD", "USDJPY"),
     "counterparties": ("the Asian and European term buyers",
                        "the international oil companies holding NFE/NFS equity",
                        "Nakilat and the Korean and Chinese yards building the fleet",
                        "the spot LNG market for the uncontracted tail"),
     "observables": ("the dated capacity announcements and FIDs",
                     "Ras Laffan berth occupancy and sailings",
                     "the PSA trade bulletin's export value by destination",
                     "each new SPA's announced tenor, volume and buyer"),
     "impact": "a dated addition of 65 mtpa to world LNG supply between 2026 and 2030 is the "
               "largest single scheduled supply event in the gas market, so the SCHEDULE is a "
               "term-structure variable for XNGUSD rather than a spot signal",
     "persistence": "years: a capacity step is permanent and a slip moves the whole curve",
     "falsifier": "XNGUSD's term structure shows no measurable response to North Field milestone "
                  "announcements once US Gulf Coast FIDs in the same quarter are controlled for; "
                  "if the US schedule explains it, this is a world-supply effect and not a "
                  "Qatari one",
     "notes": "the company is an ACTOR and never an instrument; the two-lane order forbids "
              "hunting a name and QatarEnergy is not listed in any case"},
    {"name": "Qatar Central Bank as the peg's counterparty",
     "jurisdiction": "qa",
     "holds": "the 3.6385/3.6415 riyal corridor, the QCB deposit and lending rates, and the "
              "state's foreign reserves",
     "forced_to": ("quote the corridor to licensed banks continuously",
                   "follow the Fed within hours of an FOMC decision, or explain why not",
                   "replace foreign funding from its own balance sheet when the banks lose it, "
                   "as it did through the blockade"),
     "when": "circulars follow the FOMC the same evening Doha time (about 19:30 UTC); the "
             "monetary bulletin is monthly",
     "information": ("the banks' foreign-liability position in real time",
                     "the state's deposit placements into the domestic banks",
                     "the offshore riyal's level before it is reported"),
     "constraints": ("a peg that is a political commitment, not an economic choice",
                     "reserves that are small beside the QIA but are the only ones it controls",
                     "no independent rate: the domestic cycle is the Fed's"),
     "instruments": ("USDX", "UST10Y", "XNGUSD"),
     "counterparties": ("the domestic and international banks",
                        "the Ministry of Finance and the QIA",
                        "the offshore market that priced the riyal away from 3.64 for four years"),
     "observables": ("the circular and its size relative to the Fed's step",
                     "the monthly reserve and foreign-liability lines",
                     "the QIBOR fixing and its spread to SOFR",
                     "the onshore-offshore riyal gap during a stress episode"),
     "impact": "the onshore rate cannot move, so the information is entirely in the SPREAD -- "
               "QIBOR to SOFR, onshore to offshore, QCB step to Fed step",
     "persistence": "the peg has held since 1980 and survived a four-year blockade",
     "falsifier": "the QCB-minus-Fed step and the QIBOR-SOFR spread carry no information about "
                  "USDX or UST10Y beyond what the FOMC day itself carries, measured on the same "
                  "windows with the FOMC surprise partialled out",
     "notes": "the domain GULF-C's counterparty; the blockade era is its only real sample"},
    {"name": "The Qatar Investment Authority as a rotating asset owner",
     "jurisdiction": "qa",
     "holds": "one of the largest sovereign portfolios in the world, built out of LNG revenue "
              "and rotated across public equities, private assets, real estate and sports",
     "forced_to": ("absorb the state's surplus when gas revenue exceeds the budget",
                   "fund the state when it does not, which it did through 2020",
                   "publish very little, which is itself the constraint a researcher faces"),
     "when": "transactions are disclosed when a regulator requires it -- a stake crossing a "
             "threshold, a takeover filing -- and otherwise not at all",
     "information": ("its own allocation and rotation plan",
                     "the state's fiscal position before the budget publishes it"),
     "constraints": ("almost no public disclosure obligation",
                     "size: a rotation is slow and cannot be hidden in the end",
                     "a domestic mandate that grew after the blockade -- supporting local banks "
                     "and the local market is part of the job"),
     "instruments": ("US500", "UK100", "USDX"),
     "counterparties": ("global asset managers and investment banks",
                        "the domestic banking system it recapitalised during the blockade",
                        "the co-investors in its private holdings"),
     "observables": ("regulatory threshold filings in the markets that require them",
                     "the domestic banks' foreign-liability and deposit lines",
                     "third-party size estimates, which are estimates and are labelled so"),
     "impact": "a sovereign rotation of this size is a flow into or out of the developed equity "
               "complex, but it is observable only in fragments; the honest claim is about the "
               "STATE'S fiscal position, which is computable, rather than the fund's trades",
     "persistence": "quarters to years",
     "falsifier": "periods of disclosed QIA activity show no excess move in US500 or UK100 "
                  "against matched non-activity periods -- which is the expected result, and "
                  "recording it is how this actor stops being a story",
     "notes": "carried because a Gulf pack that omits the sovereign funds has omitted the "
              "largest balance sheets in the region; the claim is deliberately weak"},
    {"name": "Ras Laffan and the Nakilat LNG fleet as the physical loading constraint",
     "jurisdiction": "qa",
     "holds": "the berths, the storage and the Q-Max/Q-Flex fleet that moves every Qatari cargo",
     "forced_to": ("load to a monthly programme agreed with the buyers",
                   "transit Hormuz on every single voyage",
                   "charter or build ahead of the capacity steps, because a train with no ship "
                   "is not supply"),
     "when": "the loading programme is set into the month boundary; sailings are continuous",
     "information": ("the nomination and berth schedule weeks ahead of any tracker",
                     "the buyers' diversion requests under the flexibility clauses"),
     "constraints": ("berth and storage capacity", "the strait", "shipyard lead times of years"),
     "instruments": ("XNGUSD", "XBRUSD"),
     "counterparties": ("the term buyers", "the shipowners and charterers",
                        "the Korean and Chinese yards"),
     "observables": ("port-call and berth statistics from Mwani Qatar",
                     "the PSA trade bulletin's volumes by destination",
                     "newbuild orders and charter announcements in the shipping press"),
     "impact": "the physical counterpart of every Qatari gas claim; a loading programme that "
               "does not rise when capacity does is the earliest sign a schedule has slipped",
     "persistence": "months",
     "falsifier": "monthly Qatari loading counts carry no information about XNGUSD beyond the "
                  "published capacity schedule and the weather, tested against matched months",
     "notes": "the observable that tells an announced capacity step from a delivered one"},
    {"name": "The Qatari Ministry of Finance and the QE's foreign investor base",
     "jurisdiction": "qa",
     "holds": "the state budget built on an assumed gas price, the USD issuance programme and "
              "the foreign-ownership regime the QE operates under",
     "forced_to": ("publish a budget with a stated oil-price assumption",
                   "issue in dollars when the assumption is missed",
                   "maintain the foreign-ownership limits that determine index weight"),
     "when": "the budget in December for the calendar year; issuance in announced windows",
     "information": ("the realised gas revenue before the trade bulletin prints it",
                     "the issuance plan"),
     "constraints": ("a budget breakeven the IMF estimates publicly",
                     "an index weight that depends on the free float it chooses to allow"),
     "instruments": ("UST10Y", "USDX", "US500"),
     "counterparties": ("the international bond market", "the global EM index funds",
                        "the QIA as the residual buyer of the surplus"),
     "observables": ("the budget's price assumption against the realised price",
                     "each issuance announcement and its size",
                     "the QE's daily net foreign flow line",
                     "the foreign-ownership limit changes, which are dated"),
     "impact": "a Qatari issuance window is a dated dollar-demand event; a foreign-ownership "
               "limit change is a dated index-weight event",
     "persistence": "days for issuance, quarters for the ownership regime",
     "falsifier": "Qatari issuance windows show no excess move in UST10Y or USDX against matched "
                  "non-issuance windows in the same month",
     "notes": "the fiscal leg of GULF-N; the IMF's published breakeven is the conditioning state"},
    # ------------------------------------------------------------------ Kuwait
    {"name": "The Central Bank of Kuwait as the setter of the daily basket rate",
     "jurisdiction": "kw",
     "holds": "the dinar's rate against an UNDISCLOSED weighted basket, the discount rate, and "
              "the only monetary discretion in the Gulf",
     "forced_to": ("announce a customer rate EVERY BUSINESS DAY, which is a daily public act",
                   "keep the basket's weights secret, which is a standing policy choice",
                   "set a discount rate that need not match the Fed's -- and in 2022-2023 "
                   "repeatedly did not"),
     "when": "the rate each business morning Asia/Kuwait (about 06:00 UTC); the discount rate "
             "when the CBK decides, often on an FOMC evening and sometimes not",
     "information": ("the basket's weights, which nobody outside the bank has",
                     "the banking system's dinar liquidity",
                     "the state's deposit position at the bank"),
     "constraints": ("a basket that must track trade partners without saying so",
                     "an economy whose revenue is dollar oil and whose imports are not",
                     "a government that cannot borrow, so the central bank's balance sheet "
                     "carries more of the adjustment than its neighbours' do"),
     "instruments": ("USDX", "EURUSD", "USDJPY"),
     "counterparties": ("the domestic banks at the daily rate",
                        "the Ministry of Finance and the General Reserve Fund",
                        "importers and the expatriate remittance corridor"),
     "observables": ("the daily published rate, which is the estimation sample",
                     "the discount-rate circular and its size against the Fed's step",
                     "the monetary statistics' public-deposit line"),
     "impact": "the only Gulf FX fixing whose change is information rather than arithmetic; the "
               "estimated non-dollar weight is a state variable for the whole GCC peg question",
     "persistence": "the basket regime has stood since 2007-05-20",
     "falsifier": "the estimated non-dollar weight from `kwd_basket_beta` is statistically "
                  "indistinguishable from zero on a long sample, which would mean the basket is "
                  "a dollar peg with extra words and GULF-D collapses into GULF-K",
     "notes": "THE distinguishing actor of this pack; everything about GULF-D starts here"},
    {"name": "The Kuwait Investment Authority and the Future Generations Fund",
     "jurisdiction": "kw",
     "holds": "the oldest sovereign wealth fund in the world, split between the Future "
              "Generations Fund and the General Reserve Fund, with its size a state secret",
     "forced_to": ("receive 10% of all state revenue into the Future Generations Fund by "
                   "statute, every year, regardless of the deficit",
                   "publish NOTHING: Law 47 of 1982 makes disclosure a criminal offence",
                   "liquidate General Reserve Fund assets when the Treasury runs short, because "
                   "the FGF is legally unreachable and there is no debt law"),
     "when": "the statutory transfer is dated to the Kuwaiti fiscal year (1 April - 31 March); "
             "the liquidations are not announced",
     "information": ("its own holdings, size and allocation -- none of which is public",
                     "the Treasury's liquidity runway"),
     "constraints": ("a law that forbids disclosure",
                     "a law that forces the transfer even in a deficit year",
                     "a General Reserve Fund that is the only spendable pot and has repeatedly "
                     "been near exhaustion"),
     "instruments": ("US500", "UK100", "UST10Y"),
     "counterparties": ("global asset managers", "the Kuwaiti Treasury",
                        "the National Assembly, which controls whether the alternative exists"),
     "observables": ("the published budget revenue line, from which the 10% is COMPUTABLE",
                     "press reports of asset swaps between the FGF and the GRF",
                     "third-party size estimates, labelled as estimates"),
     "impact": "a legally forced seller of global assets in a low-oil year and a legally forced "
               "buyer in a high-oil one -- the rarest actor shape this desk collects, and the "
               "flow is computable even though the stock is not",
     "persistence": "annual, and structural: the law has stood since 1976",
     "falsifier": "fiscal years with a computed large net FGF transfer show no measurable "
                  "difference in US500 or UST10Y against matched years, which is the honest "
                  "prior given the size of the global market",
     "notes": "NO_LAWFUL_GROUND names the disclosure ban; the flow, not the stock, is the object"},
    {"name": "Kuwait Petroleum Corporation as the OSP setter and quota holder",
     "jurisdiction": "kw",
     "holds": "Kuwait Export Crude, the OPEC quota, the refineries including Al-Zour, and the "
              "monthly official selling prices",
     "forced_to": ("announce a monthly OSP differential to the Oman/Dubai average for Asia, "
                   "after Saudi Aramco has set the reference",
                   "produce inside an OPEC quota agreed by the ministry",
                   "lift to term customers on a monthly nomination cycle"),
     "when": "the OSP in the first week of the month for the following month's liftings",
     "information": ("the term customers' nominations before the market sees them",
                     "real production against the quota"),
     "constraints": ("the Saudi OSP as the anchor it prices against",
                     "the quota", "refinery turnarounds at Al-Zour and Mina Abdullah"),
     "instruments": ("XBRUSD", "XTIUSD", "USDINR"),
     "counterparties": ("the Asian term refiners", "OPEC and the DoC",
                        "the shipowners lifting from Mina al-Ahmadi"),
     "observables": ("the monthly OSP differential",
                     "OPEC's secondary-source production estimate",
                     "JODI submissions and loading counts"),
     "impact": "an administered, dated price decision about the marginal Asian barrel; it is an "
               "EVENT with a timestamp, which is the shape this desk can test",
     "persistence": "one month by construction",
     "falsifier": "OSP announcement days show no excess XBRUSD or XTIUSD move against matched "
                  "non-announcement days in the same week, once the Saudi OSP day is controlled",
     "notes": "the Saudi OSP is the anchor, so `sa` and this pack must be mutually controlled"},
    {"name": "The Kuwaiti National Assembly as the blocker of the public debt law",
     "jurisdiction": "kw",
     "holds": "the legislative veto over sovereign borrowing, and therefore over whether the "
              "state can finance a deficit any way except by selling assets",
     "forced_to": ("approve or refuse a debt law that the government has brought repeatedly",
                   "operate in public, so the blockage is DATED and reported in Al-Qabas and "
                   "Al-Rai the same day"),
     "when": "parliamentary sessions and dissolutions -- irregular, dated, and reported",
     "information": ("the political arithmetic of the vote",
                     "the Treasury's runway as presented to it in camera"),
     "constraints": ("a constitutional relationship with the government that has produced "
                     "repeated dissolutions",
                     "a public that is the beneficiary of the spending under discussion"),
     "instruments": ("USDX", "UST10Y", "US500"),
     "counterparties": ("the Council of Ministers", "the Ministry of Finance",
                        "the rating agencies, which have cited the absence of a debt law"),
     "observables": ("the dated parliamentary votes and dissolutions",
                     "the rating agencies' actions and their stated reasons",
                     "the General Reserve Fund's reported liquidity"),
     "impact": "with no debt law, a Kuwaiti deficit is financed by SELLING GLOBAL ASSETS rather "
               "than by issuing -- which turns a fiscal event into a portfolio flow, and is the "
               "mechanism that makes GULF-E different from every other Gulf fiscal story",
     "persistence": "years; the law has been blocked for most of a decade",
     "falsifier": "dated debt-law votes and dissolutions show no measurable effect on any "
                  "executable leg, which would confine this actor to the fiscal-context role",
     "notes": "Al-Qabas is the source that covers this; no English outlet does at the same depth"},
    {"name": "The Kuwaiti Ministry of Finance and the General Reserve Fund",
     "jurisdiction": "kw",
     "holds": "the state's spendable pot, the salary bill of a majority-public workforce, and "
              "the budget that must be executed with no borrowing",
     "forced_to": ("pay salaries monthly regardless of the oil price",
                   "transfer 10% of revenue to the FGF by statute",
                   "sell or swap assets when the GRF runs short",
                   "publish a budget and a final account"),
     "when": "the fiscal year runs 1 April to 31 March -- a QUARTER AWAY from its neighbours'",
     "information": ("the GRF's actual liquidity", "the monthly execution against budget"),
     "constraints": ("no debt law", "an oil-dependent revenue line",
                     "a salary and subsidy bill that is politically fixed"),
     "instruments": ("USDX", "US500", "UST10Y"),
     "counterparties": ("the KIA as the manager of both funds", "the National Assembly",
                        "the domestic banks holding state deposits"),
     "observables": ("the budget and the final account",
                     "the CBK's public-deposit line, where a drawdown shows first",
                     "press reports of FGF-to-GRF asset swaps"),
     "impact": "a dated, statutory, oil-price-dependent flow between a sovereign portfolio and a "
               "Treasury, on a fiscal calendar that is a quarter out of phase with the rest of "
               "the Gulf -- so a 'Gulf fiscal year end' pooled study is two calendars in one",
     "persistence": "annual",
     "falsifier": "the Kuwaiti March fiscal year end shows no distinguishable effect on any "
                  "executable leg against the December year ends of its three neighbours",
     "notes": "the fiscal-calendar break is the testable part; the fund flow is the mechanism"},
    # ------------------------------------------------------------------ Oman
    {"name": "The Central Bank of Oman as the keeper of a hard peg on a thin balance sheet",
     "jurisdiction": "om",
     "holds": "the 0.3844/0.3850 rial corridor, the repo rate, and the government's "
              "Treasury-bill and sukuk programme",
     "forced_to": ("hold 0.3845 through two fiscal crises and a sub-investment-grade rating",
                   "follow the Fed through the repo rate",
                   "auction Treasury bills weekly to fund a state that borrows domestically"),
     "when": "auctions weekly; rate circulars follow the FOMC",
     "information": ("the banks' rial liquidity", "the Treasury's funding calendar"),
     "constraints": ("reserves that are small relative to the money base",
                     "a fiscal breakeven that was above the oil price for years",
                     "a peg that is a sovereign commitment and has never been revalued"),
     "instruments": ("USDX", "UST05Y", "XBRUSD"),
     "counterparties": ("the domestic banks", "the Ministry of Finance",
                        "the international bond market during the stressed years"),
     "observables": ("the weekly Treasury-bill cut-off",
                     "the OMR forward points during a stress episode",
                     "the sovereign spread and the rating actions"),
     "impact": "the Omani peg is the one the market has actually questioned, so its forward "
               "points are the Gulf's real-time devaluation-probability instrument -- and it is "
               "unquotable here, which is why the executable legs are the dollar and crude",
     "persistence": "since 1986, unrevalued",
     "falsifier": "periods of wide OMR forward points show no excess move in USDX or XBRUSD "
                  "against matched periods with the same oil price and the same Fed path",
     "notes": "the 2020 downgrade and the 2023-2024 upgrades bracket the only real sample"},
    {"name": "The Omani Ministry of Energy and Minerals as a non-OPEC OPEC+ participant",
     "jurisdiction": "om",
     "holds": "Oman's production, its Declaration of Cooperation quota, and a seat at OPEC+ "
              "without OPEC membership",
     "forced_to": ("meet a quota it did not set as an OPEC member",
                   "report production monthly through the NCSI, publicly and in detail",
                   "attend the JMMC as a non-OPEC participant"),
     "when": "the NCSI bulletin monthly; the DoC meetings on their own irregular calendar",
     "information": ("its own production and field decline before anyone else",
                     "its willingness to comply, which is the negotiation"),
     "constraints": ("mature fields with enhanced-recovery costs",
                     "a fiscal breakeven that needs volume",
                     "no OPEC vote and therefore less influence on the quota it must meet"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "counterparties": ("the DoC and its Saudi and Russian co-chairs",
                        "PDO and the international operators", "the Asian term buyers"),
     "observables": ("the NCSI monthly production and export print",
                     "the DoC's own compliance tables",
                     "the JMMC communiques"),
     "impact": "a SEPARATE QUOTA MECHANISM inside the same agreement: an OPEC compliance study "
               "that includes Oman is measuring a different contract, and one that excludes it "
               "has dropped a participant whose print is the most transparent in the group",
     "persistence": "the DoC has held since 2016 with one collapse in March 2020",
     "falsifier": "Omani compliance deviations carry no information about XBRUSD beyond the "
                  "aggregate DoC compliance number already published",
     "notes": "the membership distinction is the mechanism and is easy to pool away by accident"},
    {"name": "The Dubai Mercantile Exchange as the Oman marker's settlement process",
     "jurisdiction": "om",
     "holds": "the Oman Crude Oil Futures contract, whose settlement in a Singapore-afternoon "
              "window is the Asian sour benchmark",
     "forced_to": ("settle in a defined marker window every trading day",
                   "deliver physically against Omani loadings, which ties the paper price to a "
                   "real barrel"),
     "when": "the marker window closes 16:30 Asia/Singapore, which is 08:30 UTC all year",
     "information": ("the settlement process's own order flow, which this pack does not use",
                     "the delivery nominations"),
     "constraints": ("a deliverable grade whose volume is Oman's",
                     "competition from the Dubai assessment it sits beside"),
     "instruments": ("XBRUSD", "XTIUSD", "JPN225"),
     "counterparties": ("Asian refiners hedging sour intake",
                        "the producers setting OSPs against the marker",
                        "the physical traders arbitraging Brent-Dubai"),
     "observables": ("the published daily settlement",
                     "the Brent-Dubai relationship at the same minute",
                     "the OSP differentials struck against the marker"),
     "impact": "the Asian refining margin and every Gulf-to-Asia OSP is struck against this "
               "price at a KNOWN MINUTE, which turns a daily average into a dated event window",
     "persistence": "since the contract's 2007 launch",
     "falsifier": "the 08:30 UTC marker window shows no excess XBRUSD activity or Brent-Dubai "
                  "spread movement against matched half-hours on the same days",
     "notes": "NAMED AS A FUTURES EXCHANGE BEHIND A BENCHMARK. No order book, depth or feed is "
              "taken from it, and the crypto-venue prohibition is untouched by this row"},
    {"name": "OQ, Duqm and Ras Markaz as the Gulf's only loading points outside Hormuz",
     "jurisdiction": "om",
     "holds": "the Duqm refinery, the Ras Markaz crude storage terminal and the Sohar and "
              "Salalah ports -- all on the Arabian Sea",
     "forced_to": ("exist outside the strait, which was the point of building them",
                   "load and refine to a commercial schedule regardless of the strait's state"),
     "when": "continuous; throughput is published monthly to quarterly",
     "information": ("its own loading and storage position",
                     "the customers who route there specifically to avoid the strait"),
     "constraints": ("capacity far below the Gulf's total exports",
                     "pipeline connections that still originate inside the country"),
     "instruments": ("XBRUSD", "XTIUSD", "XNGUSD"),
     "counterparties": ("Asian refiners", "the storage lessees at Ras Markaz",
                        "the shipowners who price war risk by route"),
     "observables": ("Duqm, Sohar and Salalah throughput",
                     "Ras Markaz storage utilisation",
                     "the war-risk premium differential between inside-strait and "
                     "outside-strait loadings"),
     "impact": "THE CONTROL FOR EVERY HORMUZ CLAIM. A strait event that moves Qatari and Kuwaiti "
               "loadings and not Omani ones is a chokepoint event; one that moves both is a "
               "price event. No other Gulf pack owns a control of this shape",
     "persistence": "structural",
     "falsifier": "during dated strait-risk episodes, Omani outside-strait loadings move exactly "
                  "as much as inside-strait ones, which would mean the bypass carries no "
                  "information and GULF-H is a geography lesson",
     "notes": "`hormuz_bypass_share` is the function that encodes the split"},
    {"name": "The Oman Investment Authority as a disclosing sovereign fund",
     "jurisdiction": "om",
     "holds": "the consolidated Omani sovereign portfolio, the state's stakes in the domestic "
              "economy, and -- unusually for the Gulf -- an annual report",
     "forced_to": ("publish an annual report, which its Kuwaiti counterpart may not",
                   "support a fiscal position that was in deficit for years",
                   "privatise and list domestic assets as part of the fiscal plan"),
     "when": "the annual report yearly; divestments as announced",
     "information": ("its own allocation", "the state's privatisation pipeline"),
     "constraints": ("a portfolio smaller than its neighbours' by an order of magnitude",
                     "a domestic mandate that competes with the international one"),
     "instruments": ("US500", "USDX"),
     "counterparties": ("international asset managers",
                        "the buyers of the privatised domestic assets",
                        "the Ministry of Finance"),
     "observables": ("the annual report's allocation table",
                     "the dated divestment and listing announcements",
                     "the MSX's foreign and GCC ownership statistics"),
     "impact": "small in global terms, and its VALUE HERE IS AS THE DISCLOSING CONTROL against "
               "the KIA's legal silence: the two funds face similar oil shocks and only one of "
               "them can be read, which bounds what any Gulf sovereign-flow claim can assert",
     "persistence": "annual",
     "falsifier": "the OIA's disclosed allocation changes carry no information about any "
                  "executable leg, which is the expected result and is worth recording",
     "notes": "the honest use of this actor is as a measurement of what disclosure buys"},
    # ------------------------------------------------------------------ Bahrain
    {"name": "The Central Bank of Bahrain as the keeper of a guaranteed peg",
     "jurisdiction": "bh",
     "holds": "the 0.3760/0.3770 dinar corridor, the one-week deposit rate, BHIBOR, and the "
              "licences of the offshore wholesale banks",
     "forced_to": ("hold 0.376 on the smallest reserves in the GCC",
                   "follow the Fed",
                   "publish an interbank rate that the region reads as a stress gauge",
                   "rely, in the end, on GCC support rather than on its own balance sheet"),
     "when": "rate circulars follow the FOMC; the interbank fixing and Treasury auctions weekly",
     "information": ("the wholesale banks' funding position",
                     "the state's access to the support package"),
     "constraints": ("reserves measured in weeks of imports at the worst points",
                     "a fiscal deficit that needed an external package in 2018",
                     "a peg whose credibility is political rather than financial"),
     "instruments": ("USDX", "UST05Y", "USDTRY"),
     "counterparties": ("the domestic and wholesale banks",
                        "the Saudi, Emirati and Kuwaiti governments behind the package",
                        "the international bond market"),
     "observables": ("BHIBOR and its spread to SOFR",
                     "the BHD forward points and the sovereign spread",
                     "the rating actions and the fiscal-balance-programme reviews"),
     "impact": "THE CLEAREST 'PEG WITH AN EXTERNAL GUARANTEE' CASE IN THE WORLD: the dinar's "
               "forward prices Gulf political cohesion, so a widening is a regional signal and "
               "not a Bahraini one",
     "persistence": "since 2001; the guarantee has been tested once, in 2018, and held",
     "falsifier": "BHIBOR-minus-SOFR widening carries no information about USDX, USDTRY or the "
                  "Treasury legs beyond what the global dollar funding measures already carry",
     "notes": "the cheapest public Gulf stress gauge and the reason Bahrain earns a domain"},
    {"name": "The Bahraini Ministry of Finance and the GCC support package",
     "jurisdiction": "bh",
     "holds": "the fiscal balance programme, the USD issuance calendar, and the standing "
              "relationship with the three GCC states that underwrote the 2018 package",
     "forced_to": ("meet the fiscal-balance-programme milestones the package was conditioned on",
                   "issue in dollars into windows the market allows it",
                   "raise VAT, which it did from 5% to 10% in January 2022"),
     "when": "budgets biennially; issuance in announced windows; reviews on the programme's "
             "own calendar",
     "information": ("the programme's progress before the review publishes it",
                     "the availability of the next tranche"),
     "constraints": ("a deficit that has not closed on the original timetable",
                     "a political constraint on subsidy reform",
                     "a rating that depends on the guarantee rather than the numbers"),
     "instruments": ("UST05Y", "UST10Y", "USDX"),
     "counterparties": ("Saudi Arabia, the UAE and Kuwait as the package's underwriters",
                        "the international bond market", "the rating agencies"),
     "observables": ("the dated package announcements and disbursements",
                     "the VAT rate changes, which are dated law",
                     "each issuance and its spread"),
     "impact": "a dated external-guarantee event is the only thing that has ever moved Bahraini "
               "risk, and it moves the whole GCC cohesion trade with it",
     "persistence": "years; the 2018 package runs on a multi-year timetable",
     "falsifier": "dated package and review events show no excess move in USDTRY, USDX or the "
                  "Treasury legs against matched non-event windows",
     "notes": "the October 2018 package is the single named case and the sample is small"},
    {"name": "Bapco Energies and the Abu Safah field shared with Saudi Arabia",
     "jurisdiction": "bh",
     "holds": "the Sitra refinery, the AB pipeline from Saudi Arabia, and Bahrain's half of the "
              "Abu Safah field's production, which Saudi Arabia operates",
     "forced_to": ("depend on Saudi crude for both its refinery feed and half its oil revenue",
                   "take whatever Abu Safah produces, because it does not operate it"),
     "when": "continuous; the revenue appears in the monthly fiscal accounts",
     "information": ("the refinery's run rate and product slate",
                     "the Abu Safah allocation before the accounts print it"),
     "constraints": ("no meaningful domestic crude resource of its own",
                     "an operating dependence on a neighbour that is also the guarantor"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "counterparties": ("Saudi Aramco as the Abu Safah operator",
                        "the product buyers of the Sitra refinery",
                        "the Bahraini Treasury, which receives the revenue"),
     "observables": ("the refinery's reported throughput and the modernisation programme",
                     "the fiscal accounts' oil revenue line",
                     "Sitra loadings, which are inside the strait"),
     "impact": "Bahrain's oil revenue is a SAUDI production decision, so a Bahraini fiscal shock "
               "can be a Saudi operational event -- which is why `sa` and this pack must be "
               "mutually controlled rather than treated as independent observations",
     "persistence": "structural",
     "falsifier": "Bahraini fiscal-revenue surprises are fully explained by the crude price and "
                  "the published Abu Safah allocation, leaving no independent Bahraini signal",
     "notes": "the single clearest cross-border dependency in the GCC"},
    {"name": "The CBB-licensed offshore wholesale banks as the region's funding window",
     "jurisdiction": "bh",
     "holds": "the GCC's oldest offshore banking licence regime and a balance sheet that is "
              "regional rather than Bahraini",
     "forced_to": ("fund in dollars and lend across the GCC",
                   "report to the CBB, which publishes the aggregate",
                   "withdraw first when regional confidence turns, because the deposits are "
                   "not domestic"),
     "when": "the aggregate balance sheet is published monthly by the CBB",
     "information": ("their own cross-border exposures",
                     "the direction of GCC deposit flows before anyone reports it"),
     "constraints": ("deposits that can leave the jurisdiction in a day",
                     "a host sovereign weaker than most of their counterparties"),
     "instruments": ("USDX", "UST05Y", "USDTRY"),
     "counterparties": ("GCC corporates and sovereigns", "international banks",
                        "the CBB as regulator and lender of last resort"),
     "observables": ("the CBB's monthly banking aggregates",
                     "BHIBOR and its spread",
                     "the foreign-liability line in the aggregate balance sheet"),
     "impact": "a REGIONAL funding observable hosted in a small state: a withdrawal from these "
               "books is a Gulf-wide confidence event that prints in Bahraini statistics",
     "persistence": "months",
     "falsifier": "the wholesale banks' foreign-liability changes carry no information beyond "
                  "the global dollar funding indices already in the model",
     "notes": "the mechanism that makes a tiny economy a regional sensor"},
    {"name": "The King Fahd Causeway as Bahrain's physical demand meter",
     "jurisdiction": "bh",
     "holds": "the only road link to Saudi Arabia, and with it the weekend economy that most of "
              "Bahraini retail, hospitality and retail-gold demand runs on",
     "forced_to": ("publish traffic counts, which the authority and data.gov.bh both do",
                   "close when the border closes, which it did completely in 2020"),
     "when": "monthly statistics; the flow itself is weekly and peaks Thursday to Saturday",
     "information": ("the count, which is public",
                     "the seasonal and holiday pattern before the retail data confirms it"),
     "constraints": ("a single physical link",
                     "Saudi policy decisions that are made in Riyadh, not Manama"),
     "instruments": ("XAUUSD", "USDX"),
     "counterparties": ("Saudi visitors", "Bahraini retail, hotels and the gold souk",
                        "the two interior ministries"),
     "observables": ("monthly vehicle and passenger counts",
                     "the 2020 closure and the dated reopening",
                     "the Eid and school-holiday peaks"),
     "impact": "a COUNTED, HIGH-FREQUENCY demand series for an economy with almost no others, "
               "and its 2020 closure is the only clean natural experiment Bahrain offers",
     "persistence": "weekly seasonality with an annual Hijri overlay",
     "falsifier": "causeway counts carry no information about XAUUSD or Gulf retail demand "
                  "beyond the Hijri calendar dummies already in the model",
     "notes": "a physical observable is worth more here than another financial ratio"},
    # ------------------------------------------------------------------ shared
    {"name": "The OPEC+ ministerial and the JMMC as a dated decision body",
     "jurisdiction": "shared",
     "holds": "the quota allocation across OPEC members and non-OPEC DoC participants, and the "
              "power to change it in a called session",
     "forced_to": ("meet and publish a communique, which is a timestamped event",
                   "reconcile members and non-members inside one agreement, which is why Oman "
                   "and Qatar sit on different sides of the same table"),
     "when": "at the start of a month or in a called session; the 2023-04-02 announcement came "
             "on a Sunday, outside any meeting",
     "information": ("the negotiation before the communique",
                     "each participant's real production against its quota"),
     "constraints": ("consensus among states with opposite fiscal breakevens",
                     "compliance it cannot enforce",
                     "a shale supply response it does not control"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "counterparties": ("the member and participant states", "the physical market",
                        "the agencies whose secondary-source estimates score compliance"),
     "observables": ("the dated communiques in OPEC_PLUS_DATES",
                     "the compliance tables",
                     "the leak into the wires before the meeting"),
     "impact": "the single largest dated event class in this pack's universe; the 2020-03-06 "
               "breakdown is the largest oil event in the modern sample",
     "persistence": "one month to one quarter per decision",
     "falsifier": "OPEC+ decision days show no excess XBRUSD move against matched non-decision "
                  "days once the leak window in the preceding 48 hours is included in the event",
     "notes": "the leak window is the interesting part: a decision that is fully leaked is not "
              "an event on its own day"},
    {"name": "The MSCI and FTSE Russell index committees as dated rebalancers of GCC weight",
     "jurisdiction": "shared",
     "holds": "the classification of each Gulf market and therefore the passive flow into it",
     "forced_to": ("publish the decision and the EFFECTIVE DATE in advance",
                   "apply mechanical rules about float, foreign-ownership limits and liquidity"),
     "when": "the annual market-classification review in June, with implementations at the "
             "semi-annual and quarterly rebalance dates",
     "information": ("the rule application before the market has worked it out",
                     "the index funds' tracking obligations, which are public"),
     "constraints": ("published methodology it must follow",
                     "the exchanges' own foreign-ownership limits, which it does not set"),
     "instruments": ("US500", "UK100", "USDX"),
     "counterparties": ("global EM index funds", "the four exchanges",
                        "the active managers positioning ahead of the date"),
     "observables": ("the dated announcements and effective dates",
                     "Kuwait's COVID DELAY from May to November 2020, which is a placebo",
                     "the QE's daily net foreign flow around the dates"),
     "impact": "a MECHANICAL, PRE-ANNOUNCED flow with a known date -- the cleanest event class "
               "this region produces, and the only one where the counterparty is obliged to "
               "trade on a specific day",
     "persistence": "days around the effective date",
     "falsifier": "inclusion effective dates show no excess net foreign flow on the QE or "
                  "Boursa Kuwait against matched sessions, which would mean the flow was fully "
                  "front-run and the date carries nothing",
     "notes": "the pack's best-identified event, and the executable leg is the dollar and risk"},
    {"name": "The expatriate labour force and the month-end remittance corridor",
     "jurisdiction": "shared",
     "holds": "the majority of the workforce in all four states and a monthly salary that is "
              "largely remitted out of the region",
     "forced_to": ("be paid monthly under wage-protection systems that time the payment",
                   "remit through licensed exchange houses, which report to the central banks",
                   "send more before Eid and before the school year, which is a Hijri and a "
                   "solar seasonality at once"),
     "when": "the last and first days of each calendar month; the Eid peaks move with the Hijri "
             "calendar",
     "information": ("the corridor volumes before the balance of payments prints them",),
     "constraints": ("a wage-protection system that fixes the payment date",
                     "exchange-house pricing and the receiving countries' own controls"),
     "instruments": ("USDINR", "USDSGD", "USDZAR"),
     "counterparties": ("the exchange houses", "the receiving-country banks",
                        "the employers under the wage-protection systems"),
     "observables": ("the central banks' remittance outflow series",
                     "KNET and BENEFIT transaction volumes",
                     "the Eid and Ramadan steps in both"),
     "impact": "a dated, repeated, one-directional dollar-to-rupee flow of real size; the "
               "month-end and Eid concentration is the testable part",
     "persistence": "monthly, with an annual Hijri overlay",
     "falsifier": "Gulf month-end windows show no excess USDINR move against matched "
                  "mid-month windows once the Indian month-end itself is controlled for",
     "notes": "India, Pakistan, Bangladesh, Nepal and the Philippines are the corridors; only "
              "the rupee has an executable leg on this broker"},
    {"name": "The Asian term buyers of Gulf LNG and sour crude",
     "jurisdiction": "shared",
     "holds": "the demand side of every Qatari SPA and every Kuwaiti and Omani OSP -- the "
              "Japanese, Korean, Chinese and Indian utilities and refiners",
     "forced_to": ("nominate monthly under term contracts",
                   "run refineries against a sour crude slate whose price is the Oman marker",
                   "hedge or not hedge in markets that are public"),
     "when": "monthly nominations; the OSP response within days of the announcement",
     "information": ("their own demand and inventory before the trade data prints",
                     "their willingness to take flexible cargoes"),
     "constraints": ("refinery configuration that cannot switch crude grade quickly",
                     "government energy-security policy in all four buying countries",
                     "long-term contracts they cannot walk away from"),
     "instruments": ("JPN225", "USDKRW", "USDINR", "USDCNH"),
     "counterparties": ("QatarEnergy, KPC, OQ and the Gulf sellers",
                        "the US Gulf Coast sellers competing for the same window",
                        "the shipowners"),
     "observables": ("the PSA and NCSI export-by-destination series",
                     "each country's customs import data",
                     "the OSP differentials aimed specifically at them"),
     "impact": "the demand side that makes a Gulf supply schedule a price rather than a volume; "
               "the executable legs are the buyers' own currencies and index",
     "persistence": "months to years under term contracts",
     "falsifier": "Gulf OSP and LNG contract events carry no information about USDKRW, USDINR or "
                  "JPN225 beyond the crude and gas prices already in the model",
     "notes": "the buyers are the reason the Asian currency legs are executable instruments here"},
)

# --------------------------------------------------------------------------- domains
#: FIFTEEN DOMAINS. Qatar owns A, B and C; Kuwait D, E and O; Oman F, G and H; Bahrain I and J;
#: K, L, M and N are the shared Gulf mechanisms. Every jurisdiction owns at least two of its
#: own, which is what stops this from being one "Gulf" domain with four flags on it.
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "GULF-A", "title": "Qatar's North Field expansion as a dated LNG supply curve",
     "jurisdiction": "qa",
     "objects": ("the announced capacity steps: 77 mtpa, NFE to 110, NFS to 126, NFW to 142",
                 "the FID, EPC-award and first-cargo announcements with their dates",
                 "Ras Laffan loadings and the PSA export volumes that show delivery",
                 "the slips: an announced date that moves is itself the event"),
     "conditions": ("the capacity era the year falls in (`north_field_capacity`)",
                    "whether a US Gulf Coast FID landed in the same quarter",
                    "the European storage level at the announcement"),
     "instruments": ("XNGUSD", "XBRUSD", "USDJPY"),
     "controls": ("US Gulf Coast LNG FIDs and first cargoes in the same quarters, which "
                  "separates 'world supply schedule' from 'Qatari supply schedule'",
                  "matched quarters in which no milestone was announced",
                  "a randomised-date null drawn from the same announcement season"),
     "notes": "A PUBLISHED SUPPLY CURVE WITH DATES is the rarest object in a commodity market; "
              "the claim is about the TERM STRUCTURE, never about a spot day"},
    {"id": "GULF-B", "title": "QatarEnergy's SPA pricing: the oil-indexed to hub-indexed shift",
     "jurisdiction": "qa",
     "objects": ("the 27-year SPAs signed with Chinese and European buyers from 2022",
                 "the Brent-slope regime that preceded them",
                 "destination flexibility, which changes who can resell a cargo",
                 "the PSA export VALUE divided by VOLUME as the only public realised price"),
     "conditions": ("the pricing era: oil-indexed, mixed, or hub-referenced",
                    "the buyer's region (Asia or Europe)",
                    "whether the JKM-Brent relationship was inverted at signature"),
     "instruments": ("XNGUSD", "XBRUSD"),
     "controls": ("the same windows for US contracts, which have always been hub-indexed, "
                  "separating 'contract form' from 'gas market'",
                  "matched months with no SPA announcement",
                  "the Brent-JKM relationship in the year before each signature as the null"),
     "notes": "THE SLOPE ITSELF IS NOT PUBLISHED (NO_LAWFUL_GROUND), so this domain conditions "
              "on the ERA of the pricing regime and never on a slope series"},
    {"id": "GULF-C", "title": "The Qatari riyal: an onshore corridor and an offshore blockade",
     "jurisdiction": "qa",
     "objects": ("the 3.6385/3.6415 QCB corridor, which never moved",
                 "the offshore riyal and the forward points, which moved a great deal",
                 "the 2017-06-05 blockade and the 2021-01-05 Al-Ula declaration",
                 "the QCB and state deposit placements into the domestic banks"),
     "conditions": ("blockade era versus before and after",
                    "the QCB step against the Fed's step at each FOMC",
                    "the QIBOR-SOFR spread bucket"),
     "instruments": ("USDX", "UST10Y", "XAUUSD"),
     "controls": ("the Omani and Bahraini forward points over the same windows, which separates "
                  "'Gulf stress' from 'Qatar-specific stress'",
                  "the same windows outside the blockade era, when the offshore riyal tracked "
                  "the onshore corridor",
                  "matched FOMC days with no Gulf political news"),
     "notes": "A NAMED POLICY ERA THAT INVALIDATES POOLING: the onshore and offshore riyal were "
              "two different instruments with one name for three and a half years"},
    {"id": "GULF-D", "title": "Kuwait's undisclosed basket and its estimable dollar beta",
     "jurisdiction": "kw",
     "objects": ("the CBK's daily published customer rate",
                 "its measured sensitivity to EURUSD, USDJPY and the dollar index",
                 "the discount-rate steps that did NOT match the Fed's",
                 "the residual after the basket regression, which is the discretion"),
     "conditions": ("the estimation window's Fed regime (hiking, holding, cutting)",
                    "whether the window contains a CBK step that differed from the Fed's",
                    "the estimated non-dollar weight bucket from `kwd_basket_beta`"),
     "instruments": ("USDX", "EURUSD", "USDJPY"),
     "controls": ("the same regression run on the Qatari, Omani and Bahraini rates, which are "
                  "hard pegs and must return a slope of zero -- the strongest available placebo",
                  "a block-permuted fixing series, the null for an estimated state",
                  "the same windows in which the Fed did not move"),
     "notes": "THE ONLY GULF FX QUESTION THAT IS A QUESTION; the three hard pegs are the "
              "built-in null and that is what makes this domain cheap to falsify"},
    {"id": "GULF-E", "title": "Kuwait's fiscal law: a 10% transfer, no debt law, a forced seller",
     "jurisdiction": "kw",
     "objects": ("the statutory 10%-of-revenue Future Generations Fund transfer",
                 "the General Reserve Fund's liquidity and the reported asset swaps",
                 "the dated parliamentary votes and dissolutions on the public debt law",
                 "the March fiscal year end, a quarter away from the neighbours'"),
     "conditions": ("deficit or surplus fiscal year, computed from the published revenue",
                    "whether a debt-law vote fell in the window",
                    "the oil price against the IMF's published Kuwaiti breakeven"),
     "instruments": ("US500", "UST10Y", "USDX"),
     "controls": ("the Qatari, Omani and Bahraini December year ends over the same years, which "
                  "separates 'a fiscal year end' from 'the Kuwaiti one'",
                  "matched fiscal years with the same oil price and no debt-law event",
                  "a randomised-date null over the March boundary"),
     "notes": "the KIA's stock is UNMEASURABLE BY LAW; the FLOW is computable from the budget, "
              "and this domain is built on the flow for exactly that reason"},
    {"id": "GULF-F", "title": "Oman inside OPEC+ and outside OPEC: a separate quota mechanism",
     "jurisdiction": "om",
     "objects": ("the Declaration of Cooperation's non-OPEC participant quotas",
                 "Oman's NCSI production print against its allocation",
                 "the JMMC communiques and the dated ministerial decisions",
                 "Qatar's 2019-01-01 departure from OPEC, which changed the table's membership"),
     "conditions": ("the DoC era (2016-2020, the March 2020 collapse, 2020-2024 cuts, the "
                    "unwind)",
                    "whether the meeting was scheduled or called",
                    "Oman's own compliance bucket in the month"),
     "instruments": ("XBRUSD", "XTIUSD"),
     "controls": ("OPEC MEMBERS' compliance over the same months, which separates 'the "
                  "agreement' from 'the membership'",
                  "the same windows around scheduled meetings that produced no change",
                  "a 48-hour pre-meeting leak window as the alternative event definition"),
     "notes": "an OPEC compliance study that silently includes Oman is measuring a different "
              "contract; one that silently excludes it has dropped the clearest print"},
    {"id": "GULF-G", "title": "The DME Oman marker as the Asian sour benchmark",
     "jurisdiction": "om",
     "objects": ("the daily settlement struck in the 08:30 UTC marker window",
                 "the Brent-Dubai relationship at the same minute",
                 "the OSPs struck against the Oman/Dubai average",
                 "the NCSI realised Omani price as the physical anchor"),
     "conditions": ("the Brent-Dubai spread regime (contango or backwardation)",
                    "whether the day carried an OSP announcement",
                    "Asian refinery turnaround season"),
     "instruments": ("XBRUSD", "XTIUSD", "JPN225"),
     "controls": ("matched half-hours on the same days outside the marker window, which "
                  "separates 'the benchmark minute' from 'the day'",
                  "days in the same week with no marker-relevant news",
                  "the same window on days when the Asian physical market was closed"),
     "notes": "THE MINUTE IS THE MECHANISM. A daily average hides it and a pooled Asian-session "
              "study measures a session where the object is half an hour"},
    {"id": "GULF-H", "title": "Oman outside the strait: the Gulf's only chokepoint control",
     "jurisdiction": "om",
     "objects": ("Duqm, Ras Markaz, Sohar and Salalah throughput on the Arabian Sea",
                 "Ras Laffan, Mina al-Ahmadi and Sitra loadings inside the strait",
                 "the war-risk premium differential between the two routes",
                 "Mina al-Fahal, which is Omani AND inside the strait -- the within-country "
                 "control"),
     "conditions": ("a dated strait-risk episode versus a calm window",
                    "the inside/outside split of the loading (`hormuz_bypass_share`)",
                    "whether the episode involved shipping directly or only rhetoric"),
     "instruments": ("XBRUSD", "XTIUSD", "XNGUSD"),
     "controls": ("Omani INSIDE-strait loadings at Mina al-Fahal against Omani OUTSIDE-strait "
                  "loadings in the same episode, which holds the country constant",
                  "matched windows with the same oil price and no strait news",
                  "a randomised-date null over the episode calendar"),
     "notes": "the within-country inside/outside control is what makes this a mechanism rather "
              "than a headline, and no other Gulf pack has it"},
    {"id": "GULF-I", "title": "Bahrain: the peg with an external guarantee",
     "jurisdiction": "bh",
     "objects": ("the 0.376 corridor and the BHD forward points",
                 "the October 2018 GCC support package and its disbursements",
                 "the fiscal balance programme reviews and the VAT steps (5% in 2019, 10% in "
                 "2022)",
                 "the rating actions and their stated reasons"),
     "conditions": ("pre-package, package, and post-package era",
                    "the oil price against the IMF's published Bahraini breakeven",
                    "whether a GCC political event fell in the window"),
     "instruments": ("USDX", "UST05Y", "USDTRY"),
     "controls": ("the Omani forward points over the same windows -- a comparable weak Gulf peg "
                  "WITHOUT an explicit guarantee, which is the cleanest available contrast",
                  "matched windows with the same oil price and no package news",
                  "the same windows for the two strong pegs, Qatar and Kuwait"),
     "notes": "the guarantee is the mechanism: a Bahraini widening is a GULF COHESION signal"},
    {"id": "GULF-J", "title": "BHIBOR and the offshore wholesale banks as a regional stress gauge",
     "jurisdiction": "bh",
     "objects": ("the BHIBOR fixing and its spread to SOFR",
                 "the CBB's monthly wholesale-bank aggregates and their foreign liabilities",
                 "the King Fahd Causeway traffic as the physical demand counterpart",
                 "the Treasury-bill cut-offs"),
     "conditions": ("the spread's own bucket against its trailing distribution",
                    "whether the global dollar funding indices moved in the same window",
                    "a GCC political event in the window"),
     "instruments": ("UST05Y", "UST10Y", "USDX"),
     "controls": ("the global dollar funding measures over the same windows, which separates "
                  "'the world' from 'the Gulf'",
                  "the Qatari QIBOR-SOFR spread, the strong-peg comparison",
                  "matched windows with an unchanged spread"),
     "notes": "the cheapest public Gulf stress series, hosted by the state least able to absorb "
              "the stress it measures"},
    {"id": "GULF-K", "title": "The GCC dollar pegs as one cluster and what breaks them",
     "jurisdiction": "shared",
     "objects": ("the four parities and their corridors (`peg_band_state`)",
                 "the 2015-2016 forward-points blowout across the GCC",
                 "the March-April 2020 blowout",
                 "reserve adequacy and the IMF breakeven for each state"),
     "conditions": ("the oil price against each state's published fiscal breakeven",
                    "the peg-stress era (2015-16, 2020, or calm)",
                    "which of the four is the widest in the window"),
     "instruments": ("USDX", "XBRUSD", "USDTRY"),
     "controls": ("the Saudi and Emirati pegs over the same windows -- the `sa` and `ae` packs' "
                  "ground, which is the correct control and NOT more of the same sample",
                  "matched windows at the same oil price with no peg commentary",
                  "a block permutation of the forward-points series"),
     "notes": "FOUR PEGS ARE NOT FOUR OBSERVATIONS: they break together, so a cross-sectional "
              "study that treats them as independent is overstating its own sample by four"},
    {"id": "GULF-L", "title": "The Strait of Hormuz as a dated chokepoint risk",
     "jurisdiction": "shared",
     "objects": ("the transit volume and its share of world seaborne oil and LNG",
                 "the dated risk episodes: tanker seizures, attacks and closure threats",
                 "the war-risk premium and freight response",
                 "the inside/outside loading split that GULF-H supplies as the control"),
     "conditions": ("episode intensity: rhetoric, seizure, or damage to a vessel",
                    "whether Qatari LNG loadings were affected or only crude",
                    "the oil price level at the episode"),
     "instruments": ("XBRUSD", "XTIUSD", "XNGUSD", "XAUUSD"),
     "controls": ("Omani outside-strait loadings in the same episode",
                  "matched windows with the same oil price and no episode",
                  "gold as the generic geopolitical leg, which separates 'risk' from 'oil'"),
     "notes": "EVERY QATARI LNG CARGO transits this strait and there is no bypass, so Qatar is "
              "the most exposed LNG supplier in the world and the exposure is structural"},
    {"id": "GULF-M", "title": "The Hijri demand season: Ramadan, the two Eids and the Hajj",
     "jurisdiction": "shared",
     "objects": ("the shortened exchange sessions through Ramadan (`in_ramadan`)",
                 "the Eid closures, which are typed rather than computed",
                 "KNET and BENEFIT transaction volumes' Ramadan and Eid steps",
                 "the retail gold and food-import season"),
     "conditions": ("inside or outside the declared Ramadan window",
                    "the Eid closure length in the state concerned (`holidays_for`)",
                    "the solar month the Hijri season fell in that year"),
     "instruments": ("XAUUSD", "XAGUSD", "WHEAT", "SUGAR", "CORN"),
     "controls": ("the same solar weeks in years when Ramadan fell elsewhere, which is the "
                  "control the eleven-day drift makes possible and no month dummy can imitate",
                  "matched weekday-plus-hour windows outside the season",
                  "the non-Muslim-majority comparison markets in the same weeks"),
     "notes": "THE DRIFT IS THE IDENTIFICATION: the season walks through the solar calendar at "
              "eleven days a year, so the same solar weeks are treated and untreated across a "
              "long sample, which is a genuine natural experiment"},
    {"id": "GULF-N", "title": "GCC index inclusion as a dated, mechanical rebalance",
     "jurisdiction": "shared",
     "objects": ("Qatar's 2014 MSCI EM upgrade and Kuwait's November 2020 one",
                 "the COVID DELAY of Kuwait's implementation from May to November 2020",
                 "the QE's and Boursa Kuwait's daily net foreign flow around the dates",
                 "the foreign-ownership-limit changes that determine the weight"),
     "conditions": ("announcement window versus effective-date window",
                    "whether the effective date was rescheduled",
                    "the EM complex's own direction in the window"),
     "instruments": ("US500", "UK100", "USDX"),
     "controls": ("the delayed Kuwaiti May 2020 date as a placebo -- a date the market expected "
                  "and on which nothing was implemented",
                  "matched quarterly rebalance dates with no GCC change",
                  "the EM index's own move, which separates 'the region' from 'the flow'"),
     "notes": "the best-identified event class in the pack, because the counterparty is OBLIGED "
              "to trade on a published day"},
    {"id": "GULF-O", "title": "Kuwaiti OSPs and the OPEC+ meeting clock as dated events",
     "jurisdiction": "kw",
     "objects": ("the monthly KPC OSP differential to the Oman/Dubai average",
                 "the Saudi OSP that anchors it, announced days earlier",
                 "the OPEC+ decision dates in OPEC_PLUS_DATES",
                 "the 48-hour leak window before a ministerial"),
     "conditions": ("whether the Saudi OSP moved in the same direction",
                    "the DoC era",
                    "whether the decision was leaked before the communique"),
     "instruments": ("XBRUSD", "XTIUSD", "USDINR"),
     "controls": ("the Saudi OSP day itself, which must be partialled out or the Kuwaiti "
                  "announcement is measuring its anchor",
                  "matched non-announcement days in the same week",
                  "the same event definition with the leak window included and excluded"),
     "notes": "the anchor problem is the whole methodological content: `sa` owns the anchor and "
              "this domain owns the follower, and they must be mutually controlled"},
)

# --------------------------------------------------------------------------- the pack's miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "gulf_north_field_schedule", "domain_ids": ("GULF-A", "GULF-B"), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.gulf.pack:mine_north_field_schedule",
     "needs": ("NORTH_FIELD_SCHEDULE", "XNGUSD, XBRUSD D1 bars", "US Gulf Coast FID dates"),
     "notes": "emits the dated capacity steps as an event clock; the US FID control is named as "
              "a requirement and reported UNMEASURED when it is absent"},
    {"name": "gulf_kwd_basket", "domain_ids": ("GULF-D", "GULF-K"), "kind": "mechanism",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.gulf.pack:mine_kwd_basket",
     "needs": ("CBK:kwd_usd_daily", "EURUSD, USDJPY, USDX D1 bars"),
     "notes": "runs `kwd_basket_beta` on whatever fixing sample the context carries and runs the "
              "SAME regression on the three hard pegs as the built-in placebo"},
    {"name": "gulf_peg_stress", "domain_ids": ("GULF-C", "GULF-I", "GULF-K"), "kind": "mechanism",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.gulf.pack:mine_peg_stress",
     "needs": ("CURRENCIES", "the four forward-point series (ABSENT)", "USDX, USDTRY D1 bars"),
     "notes": "the forward points are not on this broker, so the miner emits the peg parameters "
              "and the named absence rather than a number it cannot have"},
    {"name": "gulf_hormuz_split", "domain_ids": ("GULF-H", "GULF-L"), "kind": "transfer",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.gulf.pack:mine_hormuz_split",
     "needs": ("HORMUZ_PORTS", "port throughput series", "XBRUSD, XNGUSD D1 bars"),
     "notes": "emits the inside/outside loading split that is the control for every chokepoint "
              "claim, including the within-country Mina al-Fahal comparison"},
    {"name": "gulf_hijri_season", "domain_ids": ("GULF-M",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.gulf.pack:mine_hijri_season",
     "needs": ("LUNAR_HOLIDAYS", "RAMADAN_WINDOWS", "XAUUSD, SUGAR, WHEAT H1 bars"),
     "notes": "the eleven-day drift is the identification; the miner emits the treated and the "
              "matched untreated solar weeks together or it emits nothing"},
    {"name": "gulf_event_clocks", "domain_ids": ("GULF-F", "GULF-N", "GULF-O"), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.gulf.pack:mine_event_clocks",
     "needs": ("OPEC_PLUS_DATES", "the OSP first-week calendar", "the index effective dates"),
     "notes": "the three dated event clocks with their leak windows and their placebos, "
              "including Kuwait's cancelled May 2020 index date"},
    {"name": "gulf_transmission_seeds",
     "domain_ids": ("GULF-A", "GULF-B", "GULF-E", "GULF-G", "GULF-J", "GULF-K", "GULF-L"),
     "kind": "transfer", "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.gulf.pack:mine_transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED",),
     "notes": "the pack's map as HYPOTHESIS discoveries, deduplicated by the registry"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("GULF-D", "GULF-C"),
    "release_surprise": ("GULF-F", "GULF-O"),
    "calendar_settlement": ("GULF-O", "GULF-N"),
    "holiday_liquidity": ("GULF-M",),
    "positioning": ("GULF-N",),
    "carry_funding": ("GULF-J", "GULF-K"),
    "corporate_flow": ("GULF-A", "GULF-B"),
    "institutional_flow": ("GULF-E", "GULF-N"),
    "equity_mechanics": ("GULF-N",),
    "derivatives_expiry": ("GULF-G",),
    "failure": ("GULF-L", "GULF-H"),
    "residual": ("GULF-I", "GULF-K"),
    "transfer": ("GULF-G", "GULF-L"),
    "scouts": ("GULF-H", "GULF-M"),
    "session_microstructure": ("GULF-G", "GULF-M"),
}

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "GULF-E1", "source": "North Field capacity steps (77 -> 110 -> 126 -> 142 mtpa)",
     "target": "XNGUSD", "targets": ("XNGUSD", "XBRUSD"), "to_country": "global", "sign": "-",
     "mechanism": "a dated, state-announced addition of 65 mtpa to world LNG supply between "
                  "2026 and 2030 lowers the forward curve as each step becomes credible; the "
                  "announcement, not the cargo, is the information",
     "horizon": "1 to 4 quarters", "horizon_class": "multi_day", "lag_days": 90.0,
     "actor": "QatarEnergy", "constraint": "an EPC schedule that cannot be hurried",
     "flow": "scheduled supply into the forward curve",
     "condition": "a milestone announcement with no US Gulf Coast FID in the same quarter",
     "control": "US Gulf Coast FIDs and first cargoes in the same quarters; matched quarters "
                "with no milestone",
     "falsifier": "North Field milestone quarters show no XNGUSD term-structure change once US "
                  "FIDs in the same quarter are controlled for",
     "evidence": "HYPOTHESIS"},
    {"id": "GULF-E2", "source": "QatarEnergy SPA signature with an Asian or European buyer",
     "target": "XNGUSD", "targets": ("XNGUSD", "USDJPY"), "to_country": "global", "sign": "-",
     "mechanism": "a 27-year contracted offtake removes volume from the future spot market and "
                  "moves the pricing regime away from a Brent slope toward hub indexation, "
                  "which changes the Brent-to-gas transmission function itself",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 60.0,
     "actor": "QatarEnergy and the term buyer", "constraint": "the buyer's own security policy",
     "flow": "contracted volume out of the spot market",
     "condition": "a signature announcement in the hub-indexed era",
     "control": "US contract signatures in the same months, which have always been hub-indexed",
     "falsifier": "SPA signature months carry no XNGUSD information beyond the announced volume",
     "evidence": "HYPOTHESIS"},
    {"id": "GULF-E3", "source": "The QCB step against the Fed's step at an FOMC",
     "target": "USDX", "targets": ("USDX", "UST10Y"), "to_country": "global", "sign": "+",
     "mechanism": "a Gulf peg that does NOT match the Fed is declaring a domestic funding "
                  "constraint; the deviation is a peg-stress observable and the deviations "
                  "cluster across the GCC when they happen at all",
     "horizon": "0 to 3 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "Qatar Central Bank", "constraint": "the peg and the domestic liquidity position",
     "flow": "imported policy, with a measurable residual",
     "condition": "an FOMC day on which at least one GCC central bank did not match the step",
     "control": "FOMC days on which all four matched; the FOMC surprise itself partialled out",
     "falsifier": "non-matching FOMC days are indistinguishable from matching ones on USDX",
     "evidence": "HYPOTHESIS"},
    {"id": "GULF-E4", "source": "The estimated non-dollar weight in the Kuwaiti basket",
     "target": "EURUSD", "targets": ("EURUSD", "USDX", "USDJPY"), "to_country": "global",
     "sign": "+",
     "mechanism": "the CBK's daily fixing is a public statement about how much of the dollar's "
                  "move it intends to pass through; a shift in the estimated weight is a Gulf "
                  "monetary-policy signal that no dollar peg can emit",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "Central Bank of Kuwait", "constraint": "an undisclosed basket it must still track",
     "flow": "an estimated state variable",
     "condition": "an estimation window in which `kwd_basket_beta` reports measured=true",
     "control": "the same regression on QAR, OMR and BHD, which must return zero; a "
                "block-permuted fixing series",
     "falsifier": "the estimated weight is statistically indistinguishable from zero on a long "
                  "sample, which would collapse GULF-D into GULF-K",
     "evidence": "HYPOTHESIS"},
    {"id": "GULF-E5", "source": "The computed Kuwaiti Future Generations Fund transfer in a "
                                "deficit fiscal year",
     "target": "US500", "targets": ("US500", "UST10Y", "USDX"), "to_country": "global",
     "sign": "-",
     "mechanism": "with no debt law, a deficit is financed by liquidating General Reserve Fund "
                  "assets while the statutory 10% transfer still runs -- a legally forced "
                  "seller of global assets on an annual, computable schedule",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 60.0,
     "actor": "the Kuwaiti Ministry of Finance and the KIA",
     "constraint": "Law 47/1982 and the absent debt law",
     "flow": "sovereign liquidation into the developed markets",
     "condition": "a fiscal year with a computed deficit and no debt law passed",
     "control": "the neighbours' December year ends; matched fiscal years at the same oil price",
     "falsifier": "computed large-transfer fiscal years show no US500 or UST10Y difference "
                  "against matched years, which is the honest prior",
     "evidence": "HYPOTHESIS"},
    {"id": "GULF-E6", "source": "Omani compliance deviation inside the Declaration of "
                                "Cooperation",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD"), "to_country": "global", "sign": "-",
     "mechanism": "Oman is a non-OPEC participant with the most transparent production print in "
                  "the group, so its NCSI number is an early, independent read on whether the "
                  "agreement is holding before the secondary-source tables publish",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 3.0,
     "actor": "the Omani Ministry of Energy and Minerals",
     "constraint": "mature fields and a quota it did not vote on",
     "flow": "physical barrels against an agreed allocation",
     "condition": "an NCSI print that differs from the DoC allocation by more than its own "
                  "trailing dispersion",
     "control": "OPEC members' compliance in the same months; months with no deviation",
     "falsifier": "Omani deviations carry no XBRUSD information beyond the aggregate compliance "
                  "number already published",
     "evidence": "HYPOTHESIS"},
    {"id": "GULF-E7", "source": "The DME Oman marker settlement window at 08:30 UTC",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD", "JPN225"), "to_country": "global",
     "sign": "+",
     "mechanism": "the Asian sour benchmark and every Gulf-to-Asia OSP are struck in this half "
                  "hour, so hedging and arbitrage flow concentrates there and the Brent-Dubai "
                  "spread is set at a known minute",
     "horizon": "intraday", "horizon_class": "intraday", "lag_days": 0.0,
     "actor": "Asian refiners and the physical arbitrage desks",
     "constraint": "a settlement process with a fixed close",
     "flow": "hedging into a benchmark window",
     "condition": "the 08:30 UTC half hour on a day the Asian physical market was open",
     "control": "matched half-hours on the same days; days when the Asian market was closed",
     "falsifier": "the marker half hour is indistinguishable from matched half-hours on XBRUSD",
     "evidence": "HYPOTHESIS"},
    {"id": "GULF-E8", "source": "A dated Strait of Hormuz risk episode",
     "target": "XBRUSD", "targets": ("XBRUSD", "XNGUSD", "XAUUSD", "XTIUSD"),
     "to_country": "global", "sign": "+",
     "mechanism": "a fifth of world seaborne oil and every Qatari LNG cargo transit this strait "
                  "and there is no Qatari bypass, so a credible episode is a supply-risk event "
                  "on both energy legs at once -- which is what separates it from an oil story",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "the states and non-state actors on the strait",
     "constraint": "geography; there is no alternative route for Qatari gas",
     "flow": "supply risk into the price and the war-risk premium",
     "condition": "an episode that touched shipping rather than rhetoric alone",
     "control": "Omani outside-strait loadings in the same episode; gold as the generic "
                "geopolitical leg; matched windows at the same oil price",
     "falsifier": "episodes move XBRUSD and XAUUSD identically and leave XNGUSD untouched, "
                  "which would make this a generic risk event and not a chokepoint one",
     "evidence": "MEASURED_ELSEWHERE"},
    {"id": "GULF-E9", "source": "BHIBOR minus SOFR widening",
     "target": "USDX", "targets": ("USDX", "UST05Y", "USDTRY"), "to_country": "global",
     "sign": "+",
     "mechanism": "Bahrain's offshore wholesale banks fund the region in dollars on deposits "
                  "that can leave in a day, so their funding cost widens before a Gulf "
                  "confidence event is visible anywhere else",
     "horizon": "1 to 4 weeks", "horizon_class": "multi_day", "lag_days": 5.0,
     "actor": "the CBB-licensed wholesale banks",
     "constraint": "non-domestic deposits and a weak host sovereign",
     "flow": "regional dollar funding",
     "condition": "a spread in the top decile of its trailing distribution",
     "control": "the global dollar funding measures in the same windows; the Qatari QIBOR-SOFR "
                "spread as the strong-peg comparison",
     "falsifier": "BHIBOR widening carries nothing beyond the global funding indices",
     "evidence": "HYPOTHESIS"},
    {"id": "GULF-E10", "source": "A GCC support-package or fiscal-programme event for Bahrain",
     "target": "USDTRY", "targets": ("USDTRY", "USDX", "UST05Y"), "to_country": "global",
     "sign": "-",
     "mechanism": "the Bahraini peg is held by an external guarantee, so a package event is a "
                  "GULF COHESION signal; cohesion is the same variable that prices regional "
                  "risk more broadly, and the executable regional-risk leg is the lira",
     "horizon": "0 to 10 sessions", "horizon_class": "multi_day", "lag_days": 2.0,
     "actor": "the Bahraini Ministry of Finance and the three underwriters",
     "constraint": "a deficit that has not closed on the original timetable",
     "flow": "sovereign support into regional risk premia",
     "condition": "a dated package, disbursement or programme-review announcement",
     "control": "the Omani forward points, a weak Gulf peg with no explicit guarantee; matched "
                "windows at the same oil price",
     "falsifier": "package events show no move in USDTRY or USDX against matched windows",
     "evidence": "HYPOTHESIS"},
    {"id": "GULF-E11", "source": "A GCC index-inclusion effective date (MSCI or FTSE)",
     "target": "US500", "targets": ("US500", "UK100", "USDX"), "to_country": "global",
     "sign": "+",
     "mechanism": "passive EM funds are OBLIGED to trade the weight on a published day, and the "
                  "financing of that trade is a dated dollar flow; Kuwait's cancelled May 2020 "
                  "date is the placebo the mechanism needs",
     "horizon": "0 to 5 sessions", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the MSCI and FTSE index committees and the passive funds",
     "constraint": "published methodology and a mandatory tracking obligation",
     "flow": "mechanical index flow",
     "condition": "an effective date that was not rescheduled",
     "control": "the cancelled May 2020 Kuwaiti date; quarterly rebalances with no GCC change",
     "falsifier": "effective dates show no excess net foreign flow on the QE or Boursa Kuwait "
                  "against matched sessions, which would mean the flow was fully front-run",
     "evidence": "HYPOTHESIS"},
    {"id": "GULF-E12", "source": "The Gulf month-end and Eid expatriate remittance peak",
     "target": "USDINR", "targets": ("USDINR", "USDSGD"), "to_country": "global", "sign": "+",
     "mechanism": "a majority-expatriate workforce paid monthly under wage-protection systems "
                  "produces a dated, one-directional dollar-to-rupee flow that concentrates at "
                  "the month boundary and again before each Eid",
     "horizon": "0 to 3 sessions", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the exchange houses and the expatriate workforce",
     "constraint": "the fixed payment date under the wage-protection systems",
     "flow": "remittance",
     "condition": "the last two and first two business days of a month, or the five days before "
                  "an Eid closure",
     "control": "matched mid-month windows; the Indian month-end itself partialled out",
     "falsifier": "Gulf month-end windows are indistinguishable from mid-month ones on USDINR "
                  "once the Indian month-end is controlled",
     "evidence": "HYPOTHESIS"},
    {"id": "GULF-E13", "source": "The Hijri demand season in Gulf retail gold and food imports",
     "target": "XAUUSD", "targets": ("XAUUSD", "XAGUSD", "SUGAR", "WHEAT"),
     "to_country": "global", "sign": "+",
     "mechanism": "Ramadan and the two Eids concentrate retail gold buying, wedding demand and "
                  "food imports across the Gulf, and the season drifts eleven days a year "
                  "through the solar calendar -- so the same solar weeks are treated in some "
                  "years and untreated in others",
     "horizon": "2 to 6 weeks", "horizon_class": "multi_day", "lag_days": 7.0,
     "actor": "Gulf households, the gold souks and the state food importers",
     "constraint": "the Hijri calendar, which no policy sets",
     "flow": "seasonal physical demand",
     "condition": "inside a declared Ramadan window or the five days before an Eid",
     "control": "the same solar weeks in years when the season fell elsewhere; matched "
                "weekday-plus-hour windows outside the season",
     "falsifier": "the season carries no XAUUSD or SUGAR information once the matched solar-week "
                  "control from the drift is applied",
     "evidence": "HYPOTHESIS"},
    {"id": "GULF-E14", "source": "The Kuwaiti monthly OSP differential to the Oman/Dubai average",
     "target": "XBRUSD", "targets": ("XBRUSD", "XTIUSD", "USDINR"), "to_country": "global",
     "sign": "+",
     "mechanism": "an administered, dated decision about the price of the marginal Asian barrel, "
                  "announced days after the Saudi anchor; the INCREMENT over the anchor is the "
                  "only Kuwaiti information in it",
     "horizon": "0 to 5 sessions", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "Kuwait Petroleum Corporation",
     "constraint": "the Saudi OSP it prices against and the OPEC quota",
     "flow": "administered price into the Asian term barrel",
     "condition": "an OSP day on which the Kuwaiti differential moved against the Saudi one",
     "control": "the Saudi OSP day partialled out; matched non-announcement days in the week",
     "falsifier": "Kuwaiti OSP days carry nothing once the Saudi announcement is controlled, "
                  "which would fold GULF-O entirely into the `sa` pack",
     "evidence": "HYPOTHESIS"},
)

# --------------------------------------------------------------------------- policy eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "the 77 mtpa plateau and the North Field moratorium", "start": "2005-01-01",
     "end": "2017-04-02",
     "regime": "Qatar completed the Qatargas/RasGas build-out to a 77 mtpa plateau and then "
               "placed a MORATORIUM on further North Field development in 2005, which held for "
               "twelve years; world LNG supply growth in that window was Australian and "
               "American, not Qatari",
     "markers": ("2005 the moratorium", "2010-2011 the last of the 77 mtpa trains"),
     "why_it_matters": "GULF-A's supply-schedule state CANNOT VARY here; pooling this era into "
                       "an expansion study measures a plateau and calls it a curve",
     "status": "SETTLED"},
    {"name": "the oil collapse and the first GCC peg-forward blowout", "start": "2014-06-01",
     "end": "2016-12-31",
     "regime": "Brent fell from 115 to below 30; GCC one-year forwards blew out on devaluation "
               "speculation across all six states at once, Oman and Bahrain widest; every state "
               "began issuing internationally and several introduced or planned VAT",
     "markers": ("2015-11 to 2016-02 the widest GCC forward points of the modern era",
                 "2016-11 the first Declaration of Cooperation"),
     "why_it_matters": "the FIRST of the two peg-stress samples GULF-K exists to measure, and "
                       "the four pegs moved TOGETHER, which is why they are not four "
                       "observations",
     "status": "SETTLED"},
    {"name": "the Qatar blockade", "start": "2017-06-05", "end": "2021-01-05",
     "regime": "Saudi Arabia, the UAE, Bahrain and Egypt cut diplomatic, trade and transport "
               "links with Qatar; correspondent-banking lines were withdrawn, the OFFSHORE "
               "riyal detached from 3.64 and the forward points blew out while the onshore QCB "
               "corridor never moved; the state placed deposits into the domestic banks",
     "markers": ("2017-06-05 the blockade begins", "2019-01-01 Qatar leaves OPEC",
                 "2021-01-05 the Al-Ula declaration ends it"),
     "why_it_matters": "THE NAMED ERA THAT INVALIDATES ANY POOLED QAR STUDY: onshore and "
                       "offshore were two instruments with one name, and Qatar's OPEC "
                       "membership ended inside it, which changes the GULF-F table too",
     "status": "SETTLED"},
    {"name": "the moratorium lifted and the expansion announced", "start": "2017-04-03",
     "end": "2021-02-07",
     "regime": "Qatar lifted the North Field moratorium in April 2017, raised the target from "
               "100 to 110 mtpa in 2019, and took FID on North Field East in February 2021 -- "
               "the announcements are dated and the capacity is not yet delivered",
     "markers": ("2017-04 the moratorium lifted", "2019-11 the 126 mtpa ambition stated",
                 "2021-02 NFE FID"),
     "why_it_matters": "the era in which GULF-A's state variable is an ANNOUNCEMENT and not yet "
                       "a cargo; an expansion study that pools it with delivery measures two "
                       "different mechanisms",
     "status": "SETTLED"},
    {"name": "the DoC collapse, COVID and the second peg blowout", "start": "2020-03-01",
     "end": "2020-12-31",
     "regime": "the Declaration of Cooperation broke down on 2020-03-06 and the price war began; "
               "Brent fell below 20 and WTI settled negative on 2020-04-20; the record 9.7 mb/d "
               "cut was agreed on 2020-04-12; GCC forwards blew out a second time, Oman was "
               "downgraded to sub-investment grade and the King Fahd Causeway closed entirely",
     "markers": ("2020-03-06 the DoC breakdown", "2020-04-12 the record cut",
                 "2020-05 Kuwait's MSCI implementation deferred to November"),
     "why_it_matters": "the SECOND peg-stress sample, the largest dated oil event in the modern "
                       "record, and the only complete closure of Bahrain's physical demand link",
     "status": "SETTLED"},
    {"name": "Gulf fiscal repair: VAT, support packages and the rating path",
     "start": "2019-01-01", "end": "2023-12-31",
     "regime": "Bahrain introduced VAT at 5% in January 2019 under the 2018 GCC support package "
               "and doubled it to 10% in January 2022; Oman introduced VAT in April 2021 and "
               "was returned to investment grade by 2023-2024; Kuwait passed no debt law and "
               "financed itself by asset sales throughout",
     "markers": ("2018-10 the USD 10bn Bahrain support package",
                 "2021-04 Omani VAT", "2022-01 Bahraini VAT to 10%"),
     "why_it_matters": "GULF-I and GULF-E's conditioning era: the two weak pegs diverged here, "
                       "Oman by repairing its own accounts and Bahrain by external guarantee, "
                       "which is the contrast the two domains are built on",
     "status": "SETTLED"},
    {"name": "the European gas shock and the shift to 27-year contracts",
     "start": "2022-02-24", "end": "2024-12-31",
     "regime": "the invasion of Ukraine repriced European gas; Qatar signed 27-year SPAs with "
               "Chinese and German buyers in late 2022 and further long-dated deals through "
               "2023-2024, and North Field West was announced in February 2024",
     "markers": ("2022-11 the first 27-year Chinese SPA", "2022-11 the German agreements",
                 "2024-02 North Field West announced, taking the target to 142 mtpa"),
     "why_it_matters": "GULF-B's regime break: the contract form and the buyer geography both "
                       "changed, so the Brent-to-gas transmission function is not the same "
                       "before and after",
     "status": "SETTLED"},
    {"name": "the voluntary-cut unwind and the 142 mtpa build", "start": "2025-01-01",
     "end": "2026-12-31",
     "regime": "the eight OPEC+ voluntary producers began unwinding cuts on a published "
               "schedule while Qatar builds toward 110 mtpa in 2026 and 142 by 2030; Oman "
               "remains a non-OPEC participant and Kuwait still has no debt law",
     "markers": ("2025-03 the unwind start confirmed", "2026 NFE first cargoes due"),
     "why_it_matters": "the CURRENT regime, in which a scheduled supply addition in gas meets a "
                       "scheduled supply addition in crude; every cell this pack mints today "
                       "sits in it",
     "status": "OPEN"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "none of the four currencies is quoted by this broker",
     "measured": "data/universe/universe.json holds no QAR, KWD, OMR or BHD symbol",
     "consequence": "every domestic mechanism terminates in the energy legs, the dollar legs, "
                    "gold, the Asian buyers' currencies, the Treasury tenors or the risk "
                    "indices; the four currencies are INPUTS and never cells"},
    {"constraint": "the Kuwaiti basket weights are undisclosed and the KIA discloses nothing",
     "measured": "the CBK has never published the weights; Law 47/1982 criminalises KIA "
                 "disclosure",
     "consequence": "GULF-D's state variable is ESTIMATED with its standard error by "
                    "`kwd_basket_beta`, and GULF-E is built on the statutory FLOW rather than "
                    "on a stock that legally cannot be read"},
    {"constraint": "the Dubai/Oman, JKM and tanker assessments forbid machine extraction",
     "measured": "Platts, Argus and Baltic terms; registered machine_use_allowed=false",
     "consequence": "GULF-G and GULF-L are measured on the exchange-traded crude legs and on "
                    "counted physical loadings, and the absent price is named"},
    {"constraint": "the four exchanges publish no intraday tape and no CFD quotes their indices",
     "measured": "no index symbol for QE, Boursa Kuwait, MSX or Bahrain Bourse appears in the "
                 "broker registry",
     "consequence": "GULF-N's flow is measured on the exchanges' own daily nationality "
                    "statistics and the cell is compiled on the dollar and risk legs"},
    {"constraint": "the CBK daily rate and the QE nationality pages OVERWRITE IN PLACE",
     "measured": "both publish TODAY and keep no history",
     "consequence": "the point-in-time history of the single series GULF-D depends on exists "
                    "only in the archive layer's crawls; a cell compiled on an un-archived "
                    "month is UNMEASURED rather than assumed"},
    {"constraint": "the Islamic-calendar feasts are announcements, not calculations",
     "measured": "LUNAR_HOLIDAYS is TYPED for 2024-2026 with each row naming the four sighting "
                 "authorities; 2026 is PROJECTED throughout",
     "consequence": "GULF-M may compile cells on the ANNOUNCED years and must label any cell "
                    "that depends on a 2026 date as PROJECTED until the sighting happens"},
    {"constraint": "Qatar left OPEC on 2019-01-01 and Oman was never a member",
     "measured": "the OPEC MOMR production table's membership changed under the same name",
     "consequence": "GULF-F must never pool the OPEC tables with the DoC tables; a compliance "
                    "study that does is comparing two different contracts"},
    {"constraint": "Bahrain's oil revenue is a Saudi operational decision",
     "measured": "half of Abu Safah's production accrues to Bahrain and Saudi Aramco operates it",
     "consequence": "`sa` and this pack are NOT independent observations on Gulf fiscal shocks "
                    "and must be mutually controlled in any cross-state test"},
)
INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "Qatar Exchange daily trading by nationality and investor type",
    "Boursa Kuwait daily investor-type and nationality breakdown",
    "Muscat Stock Exchange monthly foreign investment statistics",
    "Bahrain Bourse monthly ownership statistics",
    "Central Bank of Bahrain monthly wholesale-bank aggregates",
    "Central Bank of Kuwait monthly public-deposit and foreign-asset lines",
)
SERIES: dict[str, str] = {
    "GULF_KWD_FIX": "CBK:kwd_usd_daily", "GULF_KW_DISCOUNT": "CBK:discount_rate",
    "GULF_QA_DEPOSIT": "QCB:deposit_rate", "GULF_BH_IBOR": "CBB:bhibor_3m",
    "GULF_OM_TBILL": "CBO:tbill_cutoff", "GULF_OM_PRODUCTION": "NCSI:crude_production",
    "GULF_OM_EXPORTS": "NCSI:crude_exports", "GULF_QA_TRADE": "PSA:trade_exports",
    "GULF_KW_OSP": "KPC:osp_asia_differential", "GULF_NF_CAPACITY": "QE:nf_capacity_mtpa",
    "GULF_QE_FOREIGN": "QE:net_foreign_flow", "GULF_CAUSEWAY": "KFCA:monthly_crossings",
    "GULF_KNET": "KNET:transaction_volume", "GULF_BENEFIT": "BENEFIT:payment_volume",
    "GULF_OPEC_PROD": "OPEC:mom_production",
}

#: OTHER COUNTRY PACKS THIS ONE HAS A MEASURABLE INTERACTION WITH. This is how the desk stops
#: testing each country in isolation: an edge here says WHICH other pack's observable must be
#: partialled out before this pack's claim is its own.
INTERACTIONS: tuple[dict[str, Any], ...] = (
    {"with": "sa", "mechanism": "Saudi Aramco's OSP is announced days BEFORE Kuwait's and "
                                "anchors it; Saudi Aramco also OPERATES the Abu Safah field "
                                "whose output is half of Bahrain's oil revenue",
     "observable": "the Saudi OSP differential and the Abu Safah allocation",
     "targets": ("XBRUSD", "XTIUSD"),
     "control": "partial out the Saudi OSP day and the Saudi production decision before any "
                "Kuwaiti OSP or Bahraini fiscal claim is called Kuwaiti or Bahraini"},
    {"with": "ae", "mechanism": "the UAE moved to a Monday-Friday working week on 2022-01-03 "
                                "and these four did not, so the Gulf-Sunday-lead membership "
                                "CHANGED on that date; Fujairah is the other Hormuz bypass",
     "observable": "the UAE trading calendar and Fujairah's weekly product stocks",
     "targets": ("XBRUSD", "USDX"),
     "control": "split every cross-Gulf session study at 2022-01-03 and use Fujairah as the "
                "second outside-strait loading point beside Duqm"},
    {"with": "ind", "mechanism": "India is the largest single destination for Gulf remittances "
                                 "and a major buyer of Gulf sour crude and LNG, so the Gulf "
                                 "month-end flow and the Indian month-end land on the same days",
     "observable": "Indian customs crude and LNG imports; the RBI remittance series",
     "targets": ("USDINR",),
     "control": "partial out the Indian month-end and the Indian import cycle before a Gulf "
                "remittance claim on USDINR is called a Gulf claim"},
    {"with": "tr", "mechanism": "the lira is the executable regional-risk leg this pack routes "
                                "Gulf cohesion events into, and Gulf sovereign deposits in "
                                "Turkey have been a dated instrument of that cohesion",
     "observable": "dated Gulf deposit and swap announcements with Turkey",
     "targets": ("USDTRY",),
     "control": "exclude windows containing a Turkish domestic policy event, or the Gulf signal "
                "is measuring Ankara"},
    {"with": "il", "mechanism": "regional security episodes that move the Hormuz risk premium "
                                "frequently originate outside the Gulf, and the shekel is the "
                                "other executable regional-risk leg",
     "observable": "dated regional security episodes and their shipping consequences",
     "targets": ("USDILS", "XBRUSD"),
     "control": "separate episodes that touched Gulf shipping from those that did not; an "
                "episode that moves USDILS and not XNGUSD is not a chokepoint event"},
    {"with": "ru", "mechanism": "Russia is the co-chair of the Declaration of Cooperation that "
                                "sets Oman's and Kuwait's quotas, and the 2020-03-06 breakdown "
                                "was a Russian decision",
     "observable": "Russian production and the DoC negotiating position",
     "targets": ("XBRUSD", "XTIUSD"),
     "control": "partial out Russian production and Russian policy news before an Omani or "
                "Kuwaiti compliance claim is called a Gulf one"},
    {"with": "cn", "mechanism": "China is the buyer on Qatar's two longest SPAs and a growing "
                                "share of Gulf sour crude; a Chinese demand shock reaches this "
                                "pack through the contract book, not the spot market",
     "observable": "Chinese customs LNG and crude imports by origin",
     "targets": ("USDCNH", "XNGUSD"),
     "control": "condition on the Chinese import cycle before an SPA or loading claim is "
                "attributed to Qatari supply"},
    {"with": "ma", "mechanism": "the sibling MENA pack shares the Hijri calendar, so the Eid "
                                "and Ramadan seasonality is a REGIONAL seasonal and not a Gulf "
                                "one -- and Morocco's sighting frequently lands a day later",
     "observable": "the Moroccan announced Eid dates against the Gulf ones",
     "targets": ("XAUUSD", "SUGAR"),
     "control": "use Morocco's own announced dates as the out-of-Gulf control: a season effect "
                "that appears in both is Islamic-calendar seasonality, not a Gulf mechanism"},
)

# --------------------------------------------------------------------------- the testable cells
#: WHAT A CELL IS FOR. A pack's point is CELLS REACHING THE ONE GAUNTLET, so the domains, the
#: executable instruments and the named conditions are crossed HONESTLY: a cell exists only where
#: the domain itself already names that instrument and that condition, which is why this is a
#: per-domain product and not a cartesian blow-up of fifteen by twenty-four.
#: (mechanism_family, horizon) per domain -- what the gauntlet needs to file the cell.
DOMAIN_CELL_SPEC: dict[str, tuple[str, str]] = {
    "GULF-A": ("supply_schedule", "1-4 quarters"),
    "GULF-B": ("contract_regime", "1-2 quarters"),
    "GULF-C": ("peg_stress", "0-3 sessions"),
    "GULF-D": ("fixing_estimation", "1-3 months"),
    "GULF-E": ("forced_seller", "1-2 quarters"),
    "GULF-F": ("quota_compliance", "0-10 sessions"),
    "GULF-G": ("benchmark_window", "intraday"),
    "GULF-H": ("chokepoint_control", "0-10 sessions"),
    "GULF-I": ("external_guarantee", "0-10 sessions"),
    "GULF-J": ("funding_stress", "1-4 weeks"),
    "GULF-K": ("peg_cluster", "1-4 weeks"),
    "GULF-L": ("chokepoint_risk", "0-10 sessions"),
    "GULF-M": ("hijri_seasonality", "2-6 weeks"),
    "GULF-N": ("index_flow", "0-5 sessions"),
    "GULF-O": ("administered_price", "0-5 sessions"),
}


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


def mine_north_field_schedule(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The dated LNG capacity steps as an event clock (GULF-A, GULF-B)."""
    rows = [{"year": y, "mtpa": mtpa, "project": proj, "status": st}
            for y, mtpa, proj, st in NORTH_FIELD_SCHEDULE]
    emitted = sum(1 for r in rows
                  if _emit(ctx, "gulf_north_field",
                           f"{r['year']}: {r['mtpa']} mtpa -- {r['project']} [{r['status']}]"))
    return {"miner": "gulf_north_field_schedule", "rows": rows, "emitted": emitted,
            "unmeasured": ["US Gulf Coast FID dates: the control is named and not carried here"],
            "targets": ("XNGUSD", "XBRUSD", "USDJPY")}


def mine_kwd_basket(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The Kuwaiti basket estimation and its three hard-peg placebos (GULF-D, GULF-K)."""
    placebos = [peg_band_state(c, float(CURRENCIES[c]["mid"])) for c in ("QAR", "OMR", "BHD")]
    kwd = peg_band_state("KWD", float(CURRENCIES["KWD"]["mid"]))
    emitted = 1 if _emit(ctx, "gulf_kwd_basket",
                         "the CBK basket weights are undisclosed; the beta is estimated from "
                         "the published daily fixings and the three hard pegs are the "
                         "built-in null") else 0
    return {"miner": "gulf_kwd_basket", "rows": [kwd, *placebos], "emitted": emitted,
            "unmeasured": ["CBK:kwd_usd_daily is not on this tree, so no beta is estimated here; "
                           "`kwd_basket_beta` is the estimator the context must feed"],
            "targets": ("USDX", "EURUSD", "USDJPY")}


def mine_peg_stress(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The four peg parameters and the named absence of their forward points (GULF-C/I/K)."""
    rows = [{"currency": c, "regime": str(v["regime"]), "mid": v["mid"],
             "band": tuple(v.get("band") or ()), "since": str(v["since"])}
            for c, v in CURRENCIES.items()]
    emitted = sum(1 for r in rows
                  if _emit(ctx, "gulf_peg", f"{r['currency']} {r['regime']} mid={r['mid']} "
                                            f"band={r['band'] or 'UNDISCLOSED'}"))
    return {"miner": "gulf_peg_stress", "rows": rows, "emitted": emitted,
            "unmeasured": ["the QAR, OMR and BHD forward points are absent from this broker; "
                           "the peg-stress state is therefore a TRANSMISSION hypothesis and not "
                           "a compiled cell until a forward series is carried"],
            "targets": ("USDX", "USDTRY", "UST05Y")}


def mine_hormuz_split(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The inside/outside-strait loading split that controls every chokepoint claim (GULF-H/L)."""
    rows = [hormuz_bypass_share(p) for p in sorted(HORMUZ_PORTS)]
    inside = [r["port"] for r in rows if r["inside_hormuz"]]
    outside = [r["port"] for r in rows if not r["inside_hormuz"]]
    emitted = 1 if _emit(ctx, "gulf_hormuz",
                         f"inside the strait: {len(inside)}; outside: {len(outside)}; "
                         f"the within-country control is Mina al-Fahal against Duqm") else 0
    return {"miner": "gulf_hormuz_split", "rows": rows, "emitted": emitted,
            "inside": inside, "outside": outside,
            "unmeasured": ["port throughput series are named in DATASETS and not carried here"],
            "targets": ("XBRUSD", "XNGUSD", "XTIUSD")}


def mine_hijri_season(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The Ramadan windows and the typed Eid closures, with their drift (GULF-M)."""
    rows: list[dict[str, Any]] = []
    for year in sorted(RAMADAN_WINDOWS):
        lo, hi, status = RAMADAN_WINDOWS[year]
        rows.append({"year": year, "ramadan_start": lo.isoformat(), "ramadan_end": hi.isoformat(),
                     "status": status, "closures": len(market_holidays(year))})
    emitted = sum(1 for r in rows
                  if _emit(ctx, "gulf_hijri",
                           f"{r['year']}: Ramadan {r['ramadan_start']}..{r['ramadan_end']} "
                           f"[{r['status']}], {r['closures']} session-costing closures"))
    return {"miner": "gulf_hijri_season", "rows": rows, "emitted": emitted,
            "unmeasured": ["2026 is PROJECTED throughout: no 2026 sighting has happened, so a "
                           "cell compiled on a 2026 Eid date carries that label"],
            "targets": ("XAUUSD", "XAGUSD", "SUGAR", "WHEAT")}


def mine_event_clocks(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The three dated event clocks: OPEC+, the OSP first week, and index effective dates."""
    rows = [{"date": d.isoformat(), "what": what, "status": st}
            for d, what, st in OPEC_PLUS_DATES]
    emitted = sum(1 for r in rows
                  if _emit(ctx, "gulf_opec_plus", f"{r['date']}: {r['what']} [{r['status']}]"))
    return {"miner": "gulf_event_clocks", "rows": rows, "emitted": emitted,
            "unmeasured": ["the index effective dates and the monthly OSP announcements are "
                           "named in DATASETS; neither is a series on this tree"],
            "targets": ("XBRUSD", "XTIUSD", "US500")}


def mine_transmission_seeds(pack: Any = None, ctx: Any = None) -> dict[str, Any]:
    """The pack's own transmission map, emitted as HYPOTHESIS rows (every transfer domain)."""
    rows = [{"id": str(e["id"]), "target": str(e["target"]), "targets": tuple(e["targets"]),
             "evidence": str(e["evidence"]), "sign": str(e["sign"])}
            for e in TRANSMISSION_EDGES_SEED]
    emitted = sum(1 for r in rows
                  if _emit(ctx, "gulf_seed",
                           f"{r['id']} -> {', '.join(r['targets'])} [{r['evidence']}]"))
    return {"miner": "gulf_transmission_seeds", "rows": rows, "emitted": emitted,
            "unmeasured": [], "targets": tuple(sorted({t for e in TRANSMISSION_EDGES_SEED
                                                       for t in e["targets"]}))}


MINERS: dict[str, Any] = {
    "mine_north_field_schedule": mine_north_field_schedule,
    "mine_kwd_basket": mine_kwd_basket,
    "mine_peg_stress": mine_peg_stress,
    "mine_hormuz_split": mine_hormuz_split,
    "mine_hijri_season": mine_hijri_season,
    "mine_event_clocks": mine_event_clocks,
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
    return {"code": CODE.lower(), "jurisdictions": JURISDICTIONS,
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
        "terminology": TERMINOLOGY, "source_classes": SOURCE_CLASSES,
        "source_layers": SOURCE_LAYERS, "layer_absences": LAYER_ABSENCES,
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
        "north_field_schedule": NORTH_FIELD_SCHEDULE, "opec_plus_dates": OPEC_PLUS_DATES,
        "hormuz_ports": HORMUZ_PORTS, "ramadan_windows": RAMADAN_WINDOWS,
        "sighting_authorities": SIGHTING_AUTHORITIES,
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
    """The framework's HolidayRule shape: every session-costing closure the rule produces for
    2024-2026, the fixed month-days it derives them from, and the GULF weekend."""
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
