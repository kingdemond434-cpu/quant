"""INDIA: the managed rupee, the world's largest options book, and a monsoon in the CPI.

WHAT INDIA IS AS A MARKET MECHANISM, AND WHY IT IS NOT A SMALLER JAPAN. Japan's edge lives in a
zero-rate funding currency and a settlement calendar. India's lives somewhere else entirely, in
four mechanisms that no other country in this region has all four of:

  1. A CENTRAL BANK THAT SUPPRESSES REALISED VOLATILITY AS POLICY. The RBI does not target a level
     and says so, but it runs the most active FX-smoothing book in EM Asia -- spot, the forward
     book, and since 2019 the offshore NDF -- and USDINR's realised volatility has repeatedly sat
     below that of currencies with a tenth of India's capital account. The tradable consequence is
     not the level. It is that the VARIANCE is a policy variable with regime breaks at governor
     changes, so a volatility-conditioned cell on USDINR is conditioning on the RBI's reaction
     function and must be fitted inside one era rather than pooled across several.

  2. AN OPTIONS MARKET THAT IS THE WORLD'S LARGEST BY CONTRACT COUNT AND THE SMALLEST BY NOTIONAL
     PER CONTRACT. Weekly index expiry concentrates a retail-dominated open interest into one
     afternoon, and the expiry DAY ITSELF moved: Thursday for a decade, cut to one weekly per
     exchange in November 2024, then shifted to Tuesday for NSE from September 2025 under SEBI's
     expiry-day rationalisation. Any expiry-day effect measured across that boundary is an average
     over two different calendars, which is why IN-C conditions on the era and not on the weekday.
     It also hands the desk a natural experiment: if the effect FOLLOWED the expiry to Tuesday it
     is an expiry effect, and if it stayed on Thursday it was a weekday artefact all along.

  3. A GOLD IMPORT BILL THAT IS A SEASONAL, POLICY-SHOCKED CURRENT-ACCOUNT ITEM. India imports
     700-900 tonnes a year against essentially no domestic mine supply, the demand is festival-
     and wedding-dated rather than price-elastic, and the July 2024 customs-duty cut from 15% to
     6% collapsed the smuggling channel and produced record import prints that widened the trade
     deficit and moved the rupee. Gold is therefore an INDIAN MACRO INSTRUMENT here, not only a
     metal, and the edge runs XAUUSD -> import bill -> trade deficit -> USDINR.

  4. A MONSOON IN THE CONSUMER PRICE INDEX. Food and beverages carry roughly 46% of the 2012-base
     CPI basket, a weight no advanced economy comes near, so a June-September rainfall departure
     is a monetary-policy input with a two-to-five month lag -- published free and daily by the
     IMD, with sowing area published free and weekly by the agriculture ministry.

WHAT IS EXECUTABLE HERE AND WHAT IS NOT. On this broker's registry exactly ONE Indian instrument
is quotable: USDINR, a Forex Exotic with a 37-point median spread and a punishing swap asymmetry
(-480.08 per lot per night long against -42.45 short). Everything else Indian -- NIFTY, BANKNIFTY,
SENSEX, the weekly options four of these domains are about, MCX gold, the 10-year G-Sec, the
offshore NDF, India VIX -- is ABSENT, and each is named in `TRANSMISSION_TARGETS` with the
universe symbols its mechanism actually reaches. The swap asymmetry is not a footnote: a long
USDINR carry cell pays eleven times what a short pays, so every USDINR edge must clear a
DIRECTION-DEPENDENT cost floor, and IN-M exists to keep that honest.

THE TWO-LANE ORDER IS MORE LOAD-BEARING IN INDIA THAN ANYWHERE. India's retail research
vocabulary is almost entirely single-name: ValuePickr, the Moneycontrol boards and the broker PDFs
are overwhelmingly equity stories. None of that may mint a statistical hypothesis here. Single
names appear in this pack ONLY as actors -- an oil marketing company is a forced USD buyer, an IT
exporter is a forward-book seller -- and the instruments those actors move are FX, metals, energy,
softs and indices.

POINT-IN-TIME, THE INDIAN VERSION. Three publication lags dominate and every dataset row carries
its own. The RBI's Weekly Statistical Supplement reports reserves as of the PRECEDING Friday -- a
seven-day gap that has fooled more than one backtest into trading a number it could not have had.
Monthly merchandise trade lands around the 15th of the following month and the first print is
revised at the next release, so a cell must trade the first print because it is the only one that
existed. The RBI's net forward book lands in the Bulletin roughly two months in arrears, which
makes the single best intervention observable PIT-hostile by construction. NSE participant-wise
open interest is the fast one: same evening, about 18:00 IST, and therefore knowable only for the
NEXT session and never for the one it describes.

CUSTOM_MINERS ARE SPECIFICATIONS, NOT WIRING. The entries below name the module each miner will
live in and the inputs it must read. None of them is on a clock yet; unwired is a defect (III.16)
and naming it here is how the defect stays visible instead of being reported as "built".
"""
from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[3]
for _p in (str(_DESK), str(_DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.countries import (  # noqa: E402
    actor,
    build_pack,
    dataset,
    domain,
    edge,
    era,
    miner,
    source_class,
)

# --------------------------------------------------------------------------- identity
CODE = "IN"
NAME = "India"
REGION_COMMAND = "south_asia"
CURRENCY = "INR"
FISCAL_YEAR_END = "03-31"  # 1 April to 31 March; the Union Budget is read on 1 February
NATIVE_LANGUAGES: tuple[str, ...] = ("hi", "en", "mr", "gu", "ta", "bn")

#: The one Indian instrument quotable on this broker, plus the non-Indian symbols India's
#: mechanisms transmit into. No equity appears: the two-lane order keeps single names in the event
#: lane, and they enter this pack only as actors.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "USDINR",                    # the only domestic quote; spread 37 pts, swap -480.08 / -42.45
    "XAUUSD", "XAGUSD",          # the import bill and the festival demand
    "XBRUSD", "XTIUSD",          # ~85% import dependence: the structural USD bid
    "SUGAR", "SUGARRAW",         # a top-two producer whose export policy is a world supply shock
    "COTTON",                    # the world's largest area, largely rain-fed
    "WHEAT", "CORN", "SOYBEAN",  # the food-inflation complex and the export-ban instrument
    "USDCNH",                    # the EM Asia managed-currency peer India is measured against
    "USDX",                      # the dollar factor every USDINR cell must be residualised on
    "UST10Y",                    # what FAR-route index money trades the spread to
    "US500", "HK50", "CHINAH",   # the EM risk channel that sets the sign of FPI flow
    "XCUUSD",                    # infrastructure capex and its import content
)

#: Instruments these domains are ABOUT that the broker does not quote. Each names the universe
#: symbols its mechanism reaches, so an absent instrument becomes a transmission hypothesis rather
#: than a cell that can never be compiled.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "NIFTY 50 and its weekly options", "venue": "NSE",
     "why": "the expiry mechanism lives here: retail open interest concentrates into one "
            "afternoon and cash settles on the last-30-minute average",
     "proxies": ("HK50", "CHINAH", "US500", "USDINR")},
    {"name": "BANKNIFTY, FINNIFTY, MIDCPNIFTY", "venue": "NSE",
     "why": "their weeklies were withdrawn on 2024-11-20; the surviving monthly expiry still "
            "concentrates flow on the last Tuesday",
     "proxies": ("HK50", "USDINR")},
    {"name": "SENSEX weekly options", "venue": "BSE",
     "why": "the other half of the rationalisation -- BSE took Thursday when NSE took Tuesday, "
            "which makes the two exchanges' expiry effects separable for the first time",
     "proxies": ("HK50", "US500")},
    {"name": "USD/INR non-deliverable forward", "venue": "offshore (SGP, LDN, NY)",
     "why": "the onshore-offshore basis is the cleanest read on intervention intensity, and the "
            "RBI has itself traded the NDF since 2019",
     "proxies": ("USDINR", "USDCNH")},
    {"name": "MCX gold 1 kg and gold mini", "venue": "MCX",
     "why": "MCX settlement divided by USDINR is the domestic premium, which prices physical "
            "demand and the customs duty directly",
     "proxies": ("XAUUSD", "USDINR")},
    {"name": "10-year Government of India security", "venue": "NDS-OM / CCIL",
     "why": "the FAR-route index flow trades the spread to UST10Y and supply is announced in a "
            "published half-yearly borrowing calendar",
     "proxies": ("UST10Y", "USDINR")},
    {"name": "INR 40-currency nominal and real effective exchange rate", "venue": "RBI Bulletin",
     "why": "the RBI's stated object of concern is the REER; the bilateral rate is only its "
            "visible face, and a cell that forgets this mis-reads every intervention",
     "proxies": ("USDINR", "USDX", "USDCNH")},
    {"name": "India VIX", "venue": "NSE",
     "why": "the expiry-day volatility crush and the event-day term structure are read here",
     "proxies": ("HK50", "US500")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Reserve Bank of India",
    "short": "RBI",
    "committee": "Monetary Policy Committee (MPC)",
    "members": 6,
    "policy_instrument": "the policy repo rate under the liquidity adjustment facility",
    "corridor": "SDF 25bp below repo, MSF 25bp above; the OPERATIVE rate is whichever of SDF or "
                "repo the system's liquidity position pins overnight call and TREPS to, which is "
                "why a repo-rate series alone mis-describes the stance in a surplus regime",
    "mandate": "CPI inflation at 4% with a +/-2% tolerance band, reviewed every five years",
    "decision_rule": "bi-monthly: six resolutions per financial year on dates published a year "
                     "ahead in the RBI press-release calendar. A three-day sitting whose "
                     "resolution and governor's statement are read on day three at about 10:00 IST",
    "announce_local": "10:00 IST", "announce_utc": "04:30", "presser_utc": "06:30",
    "minutes_lag_days": 14,
    "off_cycle": "the MPC has met off-cycle (May 2020, May 2022); an unscheduled resolution is "
                 "announced with hours of notice and is the single largest USDINR event class",
    "other_clocks": (
        {"what": "Weekly Statistical Supplement: FX reserves, bank credit, Centre's cash balance",
         "when_local": "Friday 17:00 IST", "when_utc": "11:30", "reference_lag_days": 7},
        {"what": "RBI Bulletin: net forward book, REER, State of the Economy",
         "when_local": "mid-month", "when_utc": "11:00", "reference_lag_days": 60},
        {"what": "variable rate repo and reverse repo auctions",
         "when_local": "10:00-10:30 IST", "when_utc": "04:30", "reference_lag_days": 0},
        {"what": "G-Sec auction (Friday) and T-bill auction (Wednesday)",
         "when_local": "10:30-11:30 IST", "when_utc": "05:00", "reference_lag_days": 0},
    ),
    "dates": {
        2024: ("2024-02-08", "2024-04-05", "2024-06-07", "2024-08-08", "2024-10-09", "2024-12-06"),
        2025: ("2025-02-07", "2025-04-09", "2025-06-06", "2025-08-06", "2025-10-01", "2025-12-05"),
        2026: ("2026-02-06",),
    },
    "dates_status": "2024 and 2025 are the RBI's published FY2024-25 and FY2025-26 calendars; "
                    "2026 carries only the last resolution of FY2025-26. The FY2026-27 calendar "
                    "is published at the end of the preceding financial year, so anything after "
                    "2026-02-06 is UNMEASURED here rather than absent (L1.28a)",
}

# --------------------------------------------------------------------------- fixings, settlement
#: IST is UTC+5:30 all year with no daylight saving, so every UTC stamp below is constant -- one
#: of the few conveniences India offers a backtest, and the reason a session mask built once does
#: not silently drift twice a year the way a European one does.
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "FBIL USD/INR Reference Rate",
     "administrator": "Financial Benchmarks India Ltd",
     "window_local": "a randomly chosen one-minute window between 12:00 and 12:30 IST",
     "window_utc": "06:30-07:00", "publish_local": "about 13:30 IST", "publish_utc": "08:00",
     "basis": "volume-weighted average of USD/INR interbank spot deals in the random minute",
     "uses": "settlement reference for exchange-traded currency derivatives and for a very large "
             "share of corporate invoice conversion",
     "note": "the random-minute design exists to stop the window itself being traded; its "
             "TESTABLE consequence is that flow diffuses across the whole half hour rather than "
             "spiking in one minute, which is the opposite prediction to the London 16:00 fix"},
    {"name": "FBIL Overnight MIBOR", "administrator": "Financial Benchmarks India Ltd",
     "window_local": "09:00-10:00 IST money-market trades", "window_utc": "03:30-04:30",
     "publish_local": "about 10:45 IST", "publish_utc": "05:15",
     "basis": "volume-weighted overnight rate; computed off TREPS rather than the thin call "
              "segment since the 2025 methodology change",
     "uses": "the floating leg of the OIS curve that prices the MPC path, and therefore the "
             "benchmark a policy surprise is measured against",
     "note": "the TREPS migration is a break in the series, not a refinement of it"},
    {"name": "FBIL term MIBOR and MIFOR", "administrator": "Financial Benchmarks India Ltd",
     "window_local": "intraday polls and traded forward points", "window_utc": "06:00-07:00",
     "publish_local": "about 17:30 IST", "publish_utc": "12:00",
     "basis": "MIFOR is the USD curve plus the USD/INR forward premium",
     "uses": "the forward premium here IS the carry a USDINR CFD pays as overnight swap",
     "note": "the cleanest available public proxy for the cost this desk is actually charged"},
    {"name": "RBI reference rates for EUR, GBP and JPY against INR",
     "administrator": "RBI / FBIL", "window_local": "the same 12:00-12:30 IST window, crossed",
     "window_utc": "06:30-07:00", "publish_local": "about 13:30 IST", "publish_utc": "08:00",
     "basis": "the USD/INR fix crossed against prevailing EUR/USD, GBP/USD and USD/JPY",
     "uses": "cross-currency invoice conversion",
     "note": "these are DERIVED, not traded: an EURINR cell built on them is measuring the cross "
             "construction and not an Indian flow"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"market": "USD/INR interbank spot", "cycle": "T+2",
     "session_local": "09:00-17:00 IST", "session_utc": "03:30-11:30",
     "note": "cash and tom are quoted and actively traded, which is unusual; the cash/tom/spot "
             "ladder is where an intervention shows up before it reaches spot"},
    {"market": "NSE and BSE cash equities",
     "cycle": "T+1 since January 2023, with an optional same-day T+0 segment from March 2024",
     "session_local": "09:15-15:30 IST continuous, pre-open 09:00-09:08",
     "session_utc": "03:45-10:00",
     "note": "T+1 across a whole market of this size is a world first; it shortened the FPI "
             "funding window and changed custody pre-funding behaviour from 2023, which is a "
             "break in every foreign-flow microstructure series"},
    {"market": "exchange-traded currency derivatives",
     "cycle": "cash settled against the FBIL reference rate",
     "session_local": "09:00-17:00 IST", "session_utc": "03:30-11:30",
     "note": "the RBI's January 2024 clarification that positions require an underlying exposure "
             "cut exchange FX volumes by an order of magnitude from April 2024 -- a structural "
             "break, not an outlier, in every INR microstructure series that spans it"},
    {"market": "MCX commodities", "cycle": "physical for bullion and base metals, cash for energy",
     "session_local": "09:00-23:30 IST, 23:55 when the US is on daylight time",
     "session_utc": "03:30-18:00",
     "note": "the evening session overlaps COMEX and is the arbitrage window against XAUUSD"},
    {"market": "government securities on NDS-OM", "cycle": "T+1",
     "session_local": "09:00-17:00 IST", "session_utc": "03:30-11:30",
     "note": "FAR-route securities settle through the same pipe, which is why index inclusion "
             "needed no Euroclear link and why the flow is visible in domestic custody data"},
)

# --------------------------------------------------------------------------- exchanges
EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "National Stock Exchange of India", "code": "NSE",
     "hours_local": "09:15-15:30 IST cash and F&O; pre-open 09:00-09:08",
     "hours_utc": "03:45-10:00",
     "expiry_rule": "index options expired THURSDAY through 2025-08-28 and TUESDAY from "
                    "2025-09-02 under SEBI's expiry-day rationalisation. Only one weekly per "
                    "exchange since 2024-11-20 (NIFTY); BANKNIFTY, FINNIFTY, MIDCPNIFTY and "
                    "NIFTYNXT50 weeklies were withdrawn that day. Monthly single-stock and index "
                    "derivatives expire on the last Tuesday from September 2025",
     "settlement": "cash, at the volume-weighted average of the index over the last 30 minutes "
                   "(09:30-10:00 UTC)",
     "rebalance": "NIFTY 50 semi-annual review effective on the last trading day of March and "
                  "September, announced about four weeks ahead"},
    {"name": "BSE", "code": "BSE", "hours_local": "09:15-15:30 IST", "hours_utc": "03:45-10:00",
     "expiry_rule": "SENSEX weeklies expired Friday from 2024-11-20, moved to TUESDAY on "
                    "2025-01-01, then to THURSDAY from 2025-09-01 when NSE took Tuesday",
     "settlement": "cash, last-30-minute average",
     "rebalance": "SENSEX semi-annual, June and December"},
    {"name": "Multi Commodity Exchange", "code": "MCX",
     "hours_local": "09:00-23:30 IST, 23:55 on US daylight time", "hours_utc": "03:30-18:00",
     "expiry_rule": "gold and silver on the 5th of the contract month; crude oil on the 19th or "
                    "20th tracking NYMEX; each rolled back to the previous working day when the "
                    "date is a holiday",
     "settlement": "physical for bullion and base metals, cash for energy",
     "rebalance": "n/a"},
    {"name": "NSE currency derivatives", "code": "NSE-CD",
     "hours_local": "09:00-17:00 IST", "hours_utc": "03:30-11:30",
     "expiry_rule": "monthly futures expire two working days before the last working day of the "
                    "month; USDINR weekly options expire each Friday",
     "settlement": "cash against the FBIL reference rate",
     "rebalance": "n/a; the April 2024 underlying-exposure rule is the break in this series"},
)

# --------------------------------------------------------------------------- the holiday rule
#: The EXCHANGE holiday calendar, not the bank calendar: NSE and BSE publish a trading-holiday
#: list each December for the following calendar year, and it is the one a session-conditioned
#: cell needs. The RBI's bank-holiday list is different and is state-wise.
#:
#: Diwali is the exception that proves the point. The exchanges close for Laxmi Pujan and then
#: open for a ONE-HOUR ceremonial session, so the day is neither a holiday nor a normal session
#: and cannot be represented as a boolean. `MUHURAT` carries it separately; a cell that treats a
#: Muhurat day as a normal session is reading an hour of ceremonial volume as a full day.
_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-01-22": "Special holiday (Ram temple consecration)",
        "2024-01-26": "Republic Day",
        "2024-03-08": "Mahashivratri",
        "2024-03-25": "Holi",
        "2024-03-29": "Good Friday",
        "2024-04-11": "Id-ul-Fitr (Ramzan Id)",
        "2024-04-17": "Shri Ram Navmi",
        "2024-05-01": "Maharashtra Day",
        "2024-05-20": "Special holiday (Mumbai general election)",
        "2024-06-17": "Bakri Id",
        "2024-07-17": "Muharram",
        "2024-08-15": "Independence Day",
        "2024-10-02": "Mahatma Gandhi Jayanti",
        "2024-11-01": "Diwali Laxmi Pujan (Muhurat session only)",
        "2024-11-15": "Gurunanak Jayanti",
        "2024-12-25": "Christmas",
    },
    2025: {
        "2025-02-26": "Mahashivratri",
        "2025-03-14": "Holi",
        "2025-03-31": "Id-ul-Fitr (Ramzan Id)",
        "2025-04-10": "Shri Mahavir Jayanti",
        "2025-04-14": "Dr. Baba Saheb Ambedkar Jayanti",
        "2025-04-18": "Good Friday",
        "2025-05-01": "Maharashtra Day",
        "2025-08-15": "Independence Day",
        "2025-08-27": "Ganesh Chaturthi",
        "2025-10-02": "Mahatma Gandhi Jayanti and Dussehra",
        "2025-10-21": "Diwali Laxmi Pujan (Muhurat session only)",
        "2025-10-22": "Diwali Balipratipada",
        "2025-11-05": "Prakash Gurpurb Sri Guru Nanak Dev",
        "2025-12-25": "Christmas",
    },
    2026: {
        "2026-01-26": "Republic Day",
        "2026-03-04": "Holi",
        "2026-03-20": "Id-ul-Fitr (Ramzan Id)",
        "2026-04-03": "Good Friday",
        "2026-04-14": "Dr. Baba Saheb Ambedkar Jayanti",
        "2026-05-01": "Maharashtra Day",
        "2026-08-15": "Independence Day",
        "2026-10-02": "Mahatma Gandhi Jayanti",
        "2026-11-08": "Diwali Laxmi Pujan (Muhurat session only)",
        "2026-12-25": "Christmas",
    },
}

#: The Diwali Muhurat ceremonial session. Its TIME moves every year and is set by circular a few
#: weeks ahead: 2024 was an evening session, 2025 an afternoon one. The Lakshmi Puja tithi
#: straddled 20 and 21 October 2025 and the exchanges settled on the 21st, which is exactly why a
#: cell keyed to "the Diwali session" must read this table and not a lunar rule.
MUHURAT: dict[int, dict[str, Any]] = {
    2024: {"date": "2024-11-01", "session_local": "18:00-19:00 IST",
           "session_utc": "12:30-13:30", "samvat": 2081, "confirmed": True},
    2025: {"date": "2025-10-21", "session_local": "13:45-14:45 IST",
           "session_utc": "08:15-09:15", "samvat": 2082, "confirmed": True,
           "note": "the tithi spanned 20-21 October 2025; the exchanges traded on the 21st"},
    2026: {"date": "2026-11-08", "session_local": "set by circular", "session_utc": "",
           "samvat": 2083, "confirmed": False,
           "note": "PROVISIONAL: Diwali 2026 falls on a Sunday and the exchanges have held "
                   "Muhurat on a Sunday before; the session time is UNMEASURED until the "
                   "circular lands and must not be assumed"},
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": "NSE and BSE publish a trading-holiday circular each December for the following "
            "calendar year; that circular is the authority and the RBI's state-wise bank-holiday "
            "list is a different calendar. Weekends are Saturday and Sunday. Holi, Id-ul-Fitr, "
            "Bakri Id, Muharram, Ganesh Chaturthi, Dussehra and Diwali are lunar or luni-solar "
            "and move by up to eleven days a year, so they are TABULATED from the circulars and "
            "never computed -- a computed tithi and an exchange circular disagree often enough "
            "that the circular has to win. Diwali Laxmi Pujan is a closure that also carries a "
            "one-hour ceremonial Muhurat session, held in MUHURAT and not representable here.",
    "table": _HOLIDAYS,
    "years": (2024, 2025, 2026),
    "status": {2024: "CONFIRMED", 2025: "CONFIRMED",
               2026: "PROVISIONAL -- rebuilt from fixed national days plus lunar anchors; the "
                     "NSE circular is the authority and regional additions may differ"},
    "muhurat": MUHURAT,
    "special_sessions": "Diwali Muhurat (one hour); occasional Saturday live-trading sessions for "
                        "disaster-recovery testing, which are NOT normal sessions and must be "
                        "excluded from any session statistic",
}

# --------------------------------------------------------------------------- positioning
#: India publishes more free daily positioning data than any other market in this region, which is
#: the reason IN-D is worth mining at all. Every row names the FIELD that carries the position,
#: not just the file that holds it.
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "NSE participant-wise open interest",
     "root": "https://www.nseindia.com/all-reports",
     "fields": ("Client", "DII", "FII", "Pro", "future index long/short",
                "option index call/put long/short"),
     "frequency": "daily", "publish_utc": "12:30", "lag_days": 0, "licence": "free, public",
     "why": "the only daily, free, participant-split derivatives positioning series in EM Asia; "
            "FII net index futures is the standard regional risk-appetite proxy"},
    {"name": "NSE FII and DII cash market activity",
     "root": "https://www.nseindia.com/reports/fii-dii",
     "fields": ("FII buy value", "FII sell value", "DII buy value", "DII sell value"),
     "frequency": "daily", "publish_utc": "13:00", "lag_days": 0, "licence": "free, public",
     "why": "the DII bid is structural (monthly SIP deployment) and the FPI bid is cyclical; "
            "their DIFFERENCE is the domestic-absorption variable, not either level"},
    {"name": "NSDL FPI flows", "root": "https://www.fpi.nsdl.co.in/web/Reports/Latest.aspx",
     "fields": ("equity net", "debt net", "debt-FAR net", "hybrid", "assets under custody"),
     "frequency": "daily and fortnightly", "publish_utc": "13:30", "lag_days": 1,
     "licence": "free, public",
     "why": "the debt line separates index-tracking FAR money from discretionary money, and the "
            "two behave completely differently around an MPC"},
    {"name": "SEBI derivative statistics and the retail participation studies",
     "root": "https://www.sebi.gov.in/statistics.html",
     "fields": ("turnover", "open interest", "unique traders", "net profit and loss by cohort"),
     "frequency": "monthly and episodic", "publish_utc": "12:00", "lag_days": 30,
     "licence": "free, public",
     "why": "SEBI's own studies establish that roughly nine in ten individual F&O traders lose "
            "money; that is the standing description of who the expiry-day counterparty is"},
    {"name": "RBI net outstanding forward book",
     "root": "https://rbi.org.in/Scripts/BS_ViewBulletin.aspx",
     "fields": ("net forward purchase or sale", "maturity bucket"),
     "frequency": "monthly", "publish_utc": "11:00", "lag_days": 60, "licence": "free, public",
     "why": "spot intervention without the forward book is half the position; the book is where "
            "sterilisation hides, and the 60-day lag is what makes it PIT-hostile"},
    {"name": "CFTC Commitments of Traders (dollar index, gold, crude, sugar, cotton)",
     "root": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
     "fields": ("non-commercial net", "commercial net", "open interest"),
     "frequency": "weekly", "publish_utc": "20:30", "lag_days": 3, "licence": "free, public",
     "why": "the external leg of every India transmission edge. INR is not in it, and pretending "
            "a dollar-index COT print is INR positioning is the standard way an EM cell fools "
            "itself"},
)

# --------------------------------------------------------------------------- terminology
#: Domain-keyed native vocabulary, Devanagari first, because a Hindi source is written in
#: Devanagari and a lexical search over a Latin transliteration finds nothing. These are SEARCH
#: TOKENS for a miner, not a glossary for a reader.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "IN-A": ("रेपो दर", "मौद्रिक नीति", "मौद्रिक नीति समिति", "भारतीय रिज़र्व बैंक", "ब्याज दर",
             "मुद्रास्फीति", "तरलता", "repo rate", "MPC resolution", "stance"),
    "IN-B": ("संदर्भ दर", "विनिमय दर", "रुपया", "डॉलर", "विदेशी मुद्रा", "हस्तक्षेप",
             "reference rate", "FBIL", "NDF basis"),
    "IN-C": ("वायदा", "समाप्ति", "एक्सपायरी", "निफ्टी", "विकल्प", "ओपन इंटरेस्ट",
             "साप्ताहिक समाप्ति", "expiry day", "weekly options", "pin risk"),
    "IN-D": ("विदेशी निवेशक", "घरेलू संस्थागत निवेशक", "एफआईआई", "डीआईआई", "निवेश प्रवाह",
             "बिकवाली", "खरीदारी", "FPI flows", "DII absorption"),
    "IN-E": ("सोना", "सोने का आयात", "आयात शुल्क", "धनतेरस", "अक्षय तृतीया", "शादी का मौसम",
             "मुहूर्त व्यापार", "gold import duty", "domestic premium"),
    "IN-F": ("कच्चा तेल", "तेल आयात", "तेल विपणन कंपनी", "आयात बिल", "रूसी छूट",
             "crude import bill"),
    "IN-G": ("मानसून", "खरीफ", "रबी", "बुवाई", "वर्षा", "खाद्य मुद्रास्फीति",
             "न्यूनतम समर्थन मूल्य", "monsoon deficit", "sowing area"),
    "IN-H": ("जीएसटी", "अग्रिम कर", "राजकोषीय घाटा", "बजट", "उधारी कैलेंडर", "advance tax",
             "GST due date", "borrowing calendar"),
    "IN-I": ("महीने का अंत", "तिमाही अंत", "फॉरवर्ड प्रीमियम", "स्वैप", "हेजिंग",
             "forward premium", "fiscal year end"),
    "IN-J": ("सरकारी प्रतिभूति", "बॉन्ड सूचकांक", "एफएआर मार्ग", "विदेशी स्वामित्व",
             "index inclusion", "FAR route"),
    "IN-K": ("प्रेषण", "एनआरआई जमा", "विदेशी मुद्रा भंडार", "remittances", "NRI deposit"),
    "IN-L": ("निर्यात प्रतिबंध", "चीनी निर्यात कोटा", "चावल निर्यात", "गेहूं", "प्याज",
             "export ban", "DGFT notification"),
    "IN-M": ("कारोबारी सत्र", "एशियाई सत्र", "स्प्रेड", "लागत", "स्वैप शुल्क",
             "session handover", "carry cost", "swap asymmetry"),
}

# --------------------------------------------------------------------------- the source layers
#: THE TEN SOURCE LAYERS (principal's per-country depth rule, 2026-09-17). A country is never
#: "covered" by five obvious sources. Every layer below is either POPULATED or named in
#: `ABSENT_SOURCE_LAYERS` with a reason; blank is not an option, because a blank layer is
#: indistinguishable from a layer nobody looked at.
SOURCE_LAYERS: tuple[str, ...] = (
    "official", "institutional", "academic", "practitioner", "retail_ecology",
    "app_ecosystem", "media", "archive", "physical_economy", "source_graph")

#: The three INDEPENDENT labels every source carries. Independent on purpose: an AUTHORITATIVE
#: source can be NOT_PREDICTIVE and a FRINGE one can be PREDICTIVE. Collapsing them into a single
#: "quality" score is how a desk quietly stops looking at the material that disagrees with it.
ACCESS_LABELS: tuple[str, ...] = (
    "PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA", "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL",
    "USER_SUBMITTED", "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
CREDIBILITY_LABELS: tuple[str, ...] = (
    "AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE", "CONTRADICTED", "UNKNOWN")
PREDICTIVE_STATES: tuple[str, ...] = (
    "UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE", "NARRATIVE_FEATURE")


def _src(sid: str, label: str, *, layer: str, roots: Sequence[str], languages: Sequence[str],
         licence: str, access_label: str, credibility: str, predictive_state: str,
         queries: Sequence[str] = (), machine_use_allowed: bool = True,
         notes: str = "") -> dict[str, Any]:
    """One source class: the framework's row, plus its layer, its three labels and its queries.

    `research.countries.source_class` owns the base shape and this adds the depth-rule fields on
    top rather than replacing it, so a consumer that only knows the base shape still reads these
    rows correctly.

    `machine_use_allowed=False` means the terms of the page FORBID automated extraction. Such a
    source is REGISTERED and never scraped: it stays visible so a later session knows the material
    exists and knows why the desk has not read it, which is the opposite of omitting it.

    `queries` are the NATIVE-SCRIPT search strings for this layer, including slang. A translated
    English query against a native-language board returns nothing, and returning nothing is
    indistinguishable from the question never having been asked.
    """
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"{sid}: layer {layer!r} not one of {list(SOURCE_LAYERS)}")
    if access_label not in ACCESS_LABELS:
        raise ValueError(f"{sid}: access_label {access_label!r} unknown")
    if credibility not in CREDIBILITY_LABELS:
        raise ValueError(f"{sid}: credibility {credibility!r} unknown")
    if predictive_state not in PREDICTIVE_STATES:
        raise ValueError(f"{sid}: predictive_state {predictive_state!r} unknown")
    row = source_class(sid, label, roots=roots, languages=languages, licence=licence, notes=notes)
    row.update({"layer": layer, "access_label": access_label, "credibility": credibility,
                "predictive_state": predictive_state,
                "machine_use_allowed": bool(machine_use_allowed), "queries": tuple(queries)})
    return row


#: Layers with no source in this pack, each with the reason. Empty: all ten are populated.
ABSENT_SOURCE_LAYERS: dict[str, str] = {}

SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    _src("IN-S1", "RBI, the ministries and the statistical system", layer="official",
         roots=("https://rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx",
                "https://rbi.org.in/Scripts/WSSView.aspx", "https://dbie.rbi.org.in/",
                "https://mospi.gov.in/web/mospi/download-tables-data",
                "https://tradestat.commerce.gov.in/", "https://www.indiabudget.gov.in/"),
         languages=("en", "hi"), licence="free, public", access_label="PUBLIC",
         credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("मौद्रिक नीति "
                  "वक्तव्य",
                  "रेपो दर घोषणा",
                  "विदेशी मुद्रा "
                  "भंडार साप्ताहिक",
                  "RBI press release monetary policy", "weekly statistical supplement reserves"),
         notes="the resolution, the WSS, the Bulletin and the DBIE series, each carrying its own "
               "reference date -- which is what makes them point-in-time reconstructable at all"),
    _src("IN-S2", "regulator, exchanges and the benchmark administrator", layer="institutional",
         roots=("https://www.sebi.gov.in/statistics.html", "https://www.nseindia.com/all-reports",
                "https://www.bseindia.com/markets.html", "https://www.mcxindia.com/market-data",
                "https://www.fbil.org.in/", "https://www.fpi.nsdl.co.in/",
                "https://www.amfiindia.com/research-information"),
         languages=("en",), licence="free, public", access_label="PUBLIC",
         credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("participant wise open interest", "SEBI circular expiry day rationalisation",
                  "FBIL reference rate archive", "AMFI monthly SIP inflow",
                  "निफ्टी "
                  "समाप्ति तिथि"),
         notes="the circular archive is the ONLY reliable record of when a market-design rule "
               "changed -- the November 2024 and September 2025 expiry moves are dated here and "
               "nowhere else"),
    _src("IN-S3", "Indian academic and policy research", layer="academic",
         roots=("https://www.nipfp.org.in/publications/working-papers/",
                "https://www.icrier.org/Publications/", "https://www.igidr.ac.in/working-papers/",
                "https://rbi.org.in/Scripts/PublicationsView.aspx?id=0"),
         languages=("en",), licence="free, public", access_label="PUBLIC",
         credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("RBI intervention reaction function working paper",
                  "expiry day effect Indian options NIPFP",
                  "monsoon food inflation transmission India"),
         notes="NIPFP, ICRIER, IGIDR and the RBI's own working papers are where the intervention "
               "reaction function and the expiry-day literature are actually written down"),
    _src("IN-S4", "practitioner education and the derivatives trade's own writing",
         layer="practitioner",
         roots=("https://zerodha.com/varsity/", "https://tradingqna.com/",
                "https://sensibull.com/blog", "https://www.nseindia.com/learn"),
         languages=("en", "hi"), licence="public web; quote verbatim and attribute",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("expiry day theta decay strategy", "बैंक "
                  "निफ्टी रणनीति",
                  "short straddle expiry India", "option chain OI analysis Hindi"),
         notes="Varsity and Sensibull describe the expiry mechanics the domain IN-C is about, in "
               "the vocabulary the participants actually use. Mined as CLAIMS about mechanism, "
               "never as evidence of an effect"),
    _src("IN-S5", "retail investor boards and chat", layer="retail_ecology",
         roots=("https://forum.valuepickr.com/", "https://www.reddit.com/r/IndianStreetBets/",
                "https://www.reddit.com/r/IndiaInvestments/",
                "https://mmb.moneycontrol.com/"),
         languages=("en", "hi"), licence="public web; platform terms apply",
         access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("एक्सपायरी "
                  "डे रणनीति",
                  "expiry day scalping loss", "margin call zerodha", "operator ka stock",
                  "मल्टीबैगर"),
         notes="the expiry-day FOLKLORE lives here and most of it is wrong, which is why the "
               "label is UNRELIABLE and the row is kept anyway: SEBI's own studies say nine in "
               "ten of these participants lose money, so their collective behaviour is the "
               "counterparty IN-C is describing"),
    _src("IN-S6", "broker apps, their public APIs and the retail plumbing", layer="app_ecosystem",
         roots=("https://kite.trade/docs/connect/v3/", "https://upstox.com/developer/api/",
                "https://smartapi.angelbroking.com/docs", "https://dhanhq.co/docs/v2/",
                "https://groww.in/"),
         languages=("en",), licence="API terms vary; documentation is public",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
         predictive_state="UNTESTED",
         queries=("kite connect historical data api", "smartapi option chain",
                  "broker margin policy expiry day", "peak margin penalty"),
         notes="THE APP LAYER IS WHERE INDIA'S RETAIL OPTIONS MARKET PHYSICALLY LIVES. The broker "
               "API docs encode the exchange's own file layouts, the holiday handling and the "
               "intraday margin rules that force the expiry-day position changes IN-C studies"),
    _src("IN-S7", "Indian financial media in English and Hindi", layer="media",
         roots=("https://www.moneycontrol.com/news/business/markets/",
                "https://economictimes.indiatimes.com/markets",
                "https://www.business-standard.com/markets",
                "https://www.livemint.com/market", "https://www.zeebiz.com/hindi"),
         languages=("en", "hi"), licence="public web; quote verbatim and attribute",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("सोना आयात "
                  "शुल्क",
                  "रूपया डॉलर "
                  "के मुकाबले",
                  "DGFT notification sugar export", "gold duty cut budget"),
         notes="the Hindi business channels reach a completely different audience from the "
               "English press and move retail flow; a DGFT notification is reported in Hindi "
               "first in the agricultural belt"),
    _src("IN-S8", "the gazette and the historical archives", layer="archive",
         roots=("https://egazette.gov.in/", "https://dbie.rbi.org.in/",
                "https://web.archive.org/web/*/nseindia.com*",
                "https://eparlib.nic.in/"),
         languages=("en", "hi"), licence="free, public", access_label="PUBLIC_ARCHIVE",
         credibility="AUTHORITATIVE", predictive_state="NOT_PREDICTIVE",
         queries=("egazette customs notification gold duty",
                  "DGFT notification archive rice export", "RBI historical time series DBIE"),
         notes="THE ONLY WAY TO DATE A REGIME CHANGE CORRECTLY. A customs duty notification has a "
               "signature date and an effective date that differ, and a news article routinely "
               "conflates them. NOT_PREDICTIVE by construction: an archive establishes WHEN"),
    _src("IN-S9", "the physical economy: weather, mandis, bullion counters and ports",
         layer="physical_economy",
         roots=("https://mausam.imd.gov.in/", "https://agmarknet.gov.in/",
                "https://www.ibja.co/", "https://www.mcxindia.com/market-data/bhavcopy",
                "https://agriwelfare.gov.in/"),
         languages=("en", "hi"), licence="free, public", access_label="OPEN_DATA",
         credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("मंडी भाव "
                  "आज",
                  "वर्षा विचलन "
                  "जिला",
                  "IBJA gold rate today", "kharif sowing area weekly"),
         notes="Agmarknet publishes DAILY arrivals and prices from thousands of physical "
               "agricultural markets, free, and IBJA publishes the bullion trade's own domestic "
               "rate. This is the upstream end of IN-E and IN-G and it exists in no vendor feed"),
    _src("IN-S10", "the source graph: registries, mirrors and who publishes the same number twice",
         layer="source_graph",
         roots=("https://data.gov.in/", "https://data.worldbank.org/country/india",
                "https://comtradeplus.un.org/", "https://www.imf.org/en/Countries/IND"),
         languages=("en",), licence="open data", access_label="OPEN_DATA",
         credibility="RELIABLE", predictive_state="NOT_PREDICTIVE",
         queries=("India trade data mirror Comtrade", "data.gov.in dataset catalogue",
                  "IMF India Article IV data appendix"),
         notes="THE META LAYER, and it earns its place because India's monthly trade first print "
               "is REVISED and the mirrors carry different vintages -- so the source graph is how "
               "the desk discovers that two official numbers for the same month disagree, which "
               "is exactly the PIT problem IN-E and IN-F are exposed to"),
    _src("IN-S11", "licensed price assessors and vendor terminals", layer="institutional",
         roots=("https://www.spglobal.com/commodityinsights/en/our-methodology/",
                "https://www.lbma.org.uk/prices-and-data"),
         languages=("en",), licence="methodology free; assessments and terminal data licensed",
         access_label="LICENSED", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         machine_use_allowed=False,
         notes="REGISTERED AND NOT SCRAPED. The Indian gold premium against a licensed assessed "
               "loco-London price would be the ideal input to IN-E; the terms forbid automated "
               "extraction, so this row records that the material is known, relevant and "
               "deliberately unread. The free substitute is the MCX bhavcopy divided by USDINR"),
    _src("IN-S12", "tip channels and unverified market chatter", layer="retail_ecology",
         roots=("https://t.me/s/", "https://www.youtube.com/results?search_query=",
                "https://x.com/search"),
         languages=("en", "hi"), licence="public social; platform terms apply",
         access_label="PUBLIC_SOCIAL", credibility="FRINGE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("सुनिश्चित "
                  "मुनाफा",
                  "sureshot intraday tips", "jackpot call expiry", "operator news stock"),
         notes="FRINGE AND KEPT. SEBI has prosecuted several of these channels for manipulation, "
               "which is exactly why they are an evidence object: a coordinated tip campaign is a "
               "real crowding event even though every claim in it is false. Low weight, FRINGE "
               "label attached, never promoted to a fact, never deleted"),
)

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    dataset("RBI weekly foreign exchange reserves (WSS)", source="Reserve Bank of India",
            coverage="1998-", frequency="weekly", publication_lag_days=7,
            revisions="valuation-effect restatement only; levels are not revised",
            licence="free, public", history_from="1998-01-02", pit_feasible=True,
            assets=("USDINR", "USDX"),
            mechanism_families=("intervention", "reserve_adequacy"),
            how_to_fetch="the WSS release every Friday 17:00 IST; the REFERENCE date is the "
                         "PRECEDING Friday, and stamping the series on its reference date instead "
                         "of its publication date hands a backtest a week of hindsight on every "
                         "intervention"),
    dataset("FBIL USD/INR reference rate", source="Financial Benchmarks India Ltd",
            coverage="2018-", frequency="daily", publication_lag_days=0, revisions="none",
            licence="free, public", history_from="2018-07-10", pit_feasible=True,
            assets=("USDINR",), mechanism_families=("fixing", "flow_concentration"),
            how_to_fetch="fbil.org.in daily archive; before July 2018 the RBI published the same "
                         "fix under its own name, so the series joins but the administrator does "
                         "not"),
    dataset("NSE participant-wise open interest", source="National Stock Exchange",
            coverage="2011-", frequency="daily", publication_lag_days=0,
            revisions="occasional same-night restatement", licence="free, public",
            history_from="2011-01-03", pit_feasible=True, assets=("HK50", "US500"),
            mechanism_families=("positioning", "expiry"),
            how_to_fetch="the fao_participant_oi CSV in the NSE daily reports archive; published "
                         "about 18:00 IST, so it is knowable for the NEXT session and never for "
                         "the one it describes"),
    dataset("NSDL FPI daily and fortnightly flows", source="NSDL", coverage="2002-",
            frequency="daily", publication_lag_days=1, revisions="fortnightly true-up",
            licence="free, public", history_from="2002-04-01", pit_feasible=True,
            assets=("USDINR", "HK50"), mechanism_families=("flows", "risk_appetite"),
            how_to_fetch="fpi.nsdl.co.in reports; take the debt-FAR line separately from total "
                         "debt or index money and discretionary money are pooled"),
    dataset("monthly merchandise trade with the gold and crude lines",
            source="Ministry of Commerce and Industry / DGCIS", coverage="1996-",
            frequency="monthly", publication_lag_days=15,
            revisions="the prior month is routinely revised at each release",
            licence="free, public", history_from="1996-04-01", pit_feasible=True,
            assets=("XAUUSD", "XBRUSD", "USDINR"),
            mechanism_families=("import_bill", "terms_of_trade"),
            how_to_fetch="tradestat.commerce.gov.in commodity tables plus the monthly press "
                         "release; a cell must trade the FIRST print, which is the only one that "
                         "existed at the time"),
    dataset("CPI and the food and beverages sub-index",
            source="Ministry of Statistics and Programme Implementation", coverage="2011-",
            frequency="monthly", publication_lag_days=12, revisions="final after two months",
            licence="free, public", history_from="2011-01-01", pit_feasible=True,
            assets=("USDINR", "UST10Y"), mechanism_families=("inflation", "policy_reaction"),
            how_to_fetch="the MoSPI release on the 12th at 16:00 IST; the 2012-base series is "
                         "being replaced by a 2024-base one, and a basket change is a REGIME "
                         "BREAK in the series rather than a data error"),
    dataset("IMD daily and weekly rainfall departure",
            source="India Meteorological Department",
            coverage="1901- annual, 2001- for the daily district grid", frequency="daily",
            publication_lag_days=1, revisions="quality-control restatement within a week",
            licence="free, public", history_from="2001-06-01", pit_feasible=True,
            assets=("WHEAT", "CORN", "SUGAR", "COTTON"),
            mechanism_families=("weather", "food_inflation", "sowing"),
            how_to_fetch="the IMD hydromet district rainfall tables and the April and May "
                         "long-range forecast press releases"),
    dataset("weekly kharif and rabi sowing area",
            source="Department of Agriculture and Farmers Welfare", coverage="2010-",
            frequency="weekly in season", publication_lag_days=3,
            revisions="cumulative and revised weekly", licence="free, public",
            history_from="2010-06-01", pit_feasible=True,
            assets=("SUGAR", "COTTON", "SOYBEAN", "CORN"),
            mechanism_families=("supply", "food_inflation"),
            how_to_fetch="the weekly crop-sowing press release; cumulative area by crop against "
                         "the same week of the prior year"),
    dataset("MCX gold and silver daily settlement", source="Multi Commodity Exchange",
            coverage="2003-", frequency="daily", publication_lag_days=0, revisions="none",
            licence="free for the daily bhavcopy", history_from="2003-11-10", pit_feasible=True,
            assets=("XAUUSD", "XAGUSD", "USDINR"),
            mechanism_families=("local_premium", "import_demand"),
            how_to_fetch="the MCX bhavcopy; divide by USDINR and by 31.1035 to express the "
                         "domestic premium in USD per ounce, then subtract the duty in force"),
    dataset("RBI MPC resolutions, statements and minutes", source="Reserve Bank of India",
            coverage="2016-", frequency="six per financial year", publication_lag_days=0,
            revisions="none; minutes 14 days later", licence="free, public",
            history_from="2016-10-04", pit_feasible=True, assets=("USDINR", "UST10Y"),
            mechanism_families=("policy_event", "tone"),
            how_to_fetch="the press-release archive; the MINUTES are a second event with their "
                         "own dissent count and are routinely ignored as stale"),
    dataset("Union Budget documents and the half-yearly borrowing calendar",
            source="Ministry of Finance", coverage="2000-",
            frequency="annual plus two calendars", publication_lag_days=0,
            revisions="revised estimates in the following budget", licence="free, public",
            history_from="2000-02-01", pit_feasible=True, assets=("UST10Y", "USDINR"),
            mechanism_families=("fiscal", "supply"),
            how_to_fetch="indiabudget.gov.in for the documents; the H1 calendar lands in late "
                         "March and the H2 calendar in late September"),
    dataset("monthly GST collections", source="Ministry of Finance / GSTN", coverage="2017-",
            frequency="monthly", publication_lag_days=1, revisions="none",
            licence="free, public", history_from="2017-07-01", pit_feasible=True,
            assets=("USDINR",), mechanism_families=("activity_nowcast", "liquidity"),
            how_to_fetch="the press release on the 1st for the preceding month -- the fastest "
                         "activity nowcast India publishes and the only one with a one-day lag"),
)

# --------------------------------------------------------------------------- the actors
ACTORS: tuple[dict[str, Any], ...] = (
    actor(
        "RBI foreign exchange operations desk",
        holds="around USD 690-700bn of reserves plus a large net forward book, run against a "
              "stated objective of curbing excessive volatility rather than defending a level",
        forced_to=("absorb dollar inflows in surplus periods so nominal appreciation does not "
                   "erode export competitiveness",
                   "sell dollars into depreciation episodes so imported inflation does not feed "
                   "a CPI target it is legally accountable for",
                   "sterilise the rupee consequence through VRRR, CRR and bond sales"),
        when="continuously through the 03:30-11:30 UTC onshore window, concentrated around the "
             "06:30-07:00 UTC fixing window and at month end",
        information=("interbank order flow it sees as the settlement bank",
                     "daily FPI custody flow before it is published",
                     "oil marketing company dollar demand schedules",
                     "the offshore NDF basis, which it now trades itself"),
        constraints=("a 4% CPI target with a +/-2% band",
                     "reserve adequacy metrics the rating agencies read",
                     "the fiscal cost of sterilisation on its own balance sheet",
                     "the US Treasury currency report's thresholds on net purchases"),
        instruments=("USDINR", "USDCNH", "UST10Y"),
        counterparties=("public sector banks acting as its agents", "foreign bank branches",
                        "offshore NDF market makers"),
        observables=("weekly reserves in the WSS", "the monthly net forward book",
                     "realised versus implied USDINR volatility", "the onshore-offshore basis"),
        impact="compresses realised volatility and truncates the distribution's tails, turning "
               "USDINR into long quiet regimes punctuated by rare step changes -- the exact shape "
               "that flatters a mean-reversion backtest and then ruins it live",
        persistence="structural since 1993 and re-affirmed at every governor transition; the "
                    "INTENSITY changes with the governor, which is why the eras below are cut at "
                    "governors rather than at calendar years",
        falsifier="a quarter in which USDINR 21-day realised volatility exceeds the EM Asia "
                  "median with reserves unchanged would say the desk has stopped operating, and "
                  "every volatility-conditioned cell here would need re-fitting"),
    actor(
        "Public sector oil marketing companies",
        holds="the import book for roughly 85% of India's 5.0-5.5 million barrels a day of crude "
              "consumption",
        forced_to=("buy dollars daily to pay cargo invoices priced off dated Brent",
                   "hold exposure unhedged when the government prefers it and the rupee looks "
                   "pinned",
                   "absorb retail price freezes before elections without a pass-through"),
        when="daily dollar purchases concentrated in the 05:00-09:00 UTC onshore morning, with "
             "invoice settlement clustering at month end",
        information=("their own cargo schedules", "the discount offered on Russian barrels",
                     "refinery maintenance calendars"),
        constraints=("state ownership and an implicit obligation not to pass shocks to the pump "
                     "before an election",
                     "working-capital limits that force spot conversion rather than forwards"),
        instruments=("USDINR", "XBRUSD", "XTIUSD"),
        counterparties=("Gulf and Russian sellers",
                        "the RBI when it supplies dollars directly through a special window, as "
                        "in 2013 and 2022"),
        observables=("monthly crude import volume and value in the trade data",
                     "the Brent-Dubai spread", "the Russian discount", "retail price freezes"),
        impact="a structural, price-inelastic dollar bid that makes USDINR co-move with the oil "
               "bill monthly and with the RBI's willingness to supply dollars daily",
        persistence="permanent while import dependence stays above 80%; the post-2022 shift to "
                    "Russian barrels changed the settlement currency for part of the flow and is "
                    "a genuine break in the relationship",
        falsifier="a month in which the crude import bill rises more than 20% year on year with "
                  "USDINR and reserves both unchanged would break the flow link"),
    actor(
        "Foreign portfolio investors in Indian equities",
        holds="roughly 16-18% of the free float of Indian listed equity",
        forced_to=("rebalance against EM benchmark weights when India's weight changes",
                   "convert and repatriate on redemption",
                   "fund T+1 settlement onshore rather than at leisure"),
        when="custody flow settles T+1 and the NSDL print lands about 13:30 UTC the next day",
        information=("global EM fund flow data", "index provider consultations",
                     "the domestic earnings cycle"),
        constraints=("MSCI and FTSE weights", "a 10% single-company limit per FPI",
                     "the short-term capital gains regime raised in the July 2024 budget"),
        instruments=("USDINR", "HK50", "CHINAH", "US500"),
        counterparties=("domestic mutual funds absorbing their selling", "insurance companies",
                        "the RBI through the currency leg"),
        observables=("NSDL daily FPI equity net", "NSE FII cash activity",
                     "FII net index futures position"),
        impact="the marginal buyer of Indian equity risk and the marginal seller of rupees; its "
               "sign flips faster than the domestic bid, so the FPI-minus-DII difference is the "
               "variable rather than either level",
        persistence="cyclical with the global EM cycle; the PRICE impact per rupee of FPI selling "
                    "has fallen materially since 2021 as domestic absorption grew",
        falsifier="a quarter of FPI equity outflow above USD 8bn during which the index rises and "
                  "USDINR falls would say the flow no longer sets the marginal price"),
    actor(
        "Index-tracking foreign holders of FAR-route government bonds",
        holds="the Fully Accessible Route securities that entered JPMorgan's GBI-EM from June "
              "2024, Bloomberg's EM local index from January 2025 and FTSE Russell's thereafter",
        forced_to=("buy to weight on each phase-in date regardless of price",
                   "rebalance monthly with the index"),
        when="phase-in dates are pre-announced; monthly index rebalances fall on the last "
             "business day",
        information=("index rules published years ahead",
                     "the Ministry of Finance borrowing calendar"),
        constraints=("tracking error against a published benchmark",
                     "no withholding-tax exemption, which caps the natural holder base"),
        instruments=("UST10Y", "USDINR"),
        counterparties=("primary dealers", "domestic banks running down excess SLR",
                        "the RBI's open market operations"),
        observables=("NSDL debt-FAR net flows", "the 10-year spread to UST10Y",
                     "the announced phase-in schedule itself"),
        impact="a price-insensitive and DATE-KNOWN buyer, so the flow is forecastable and already "
               "partly in the price; the interesting cell is the gap between the announced "
               "schedule and the realised flow, never the schedule",
        persistence="structural for the weight and transitory for the phase-in; the phase-in "
                    "ended in 2025 and cannot be re-mined",
        falsifier="a phase-in month with no measurable debt-FAR inflow in the NSDL series"),
    actor(
        "Domestic institutional investors and the monthly SIP flow",
        holds="a systematic investment plan book running above INR 280bn a month, plus insurance "
              "and pension mandates",
        forced_to=("deploy on fixed monthly dates regardless of the level",
                   "absorb FPI selling, because redemption is slower than subscription"),
        when="SIP debits cluster in the first week and around the 10th of each month",
        information=("their own subscription book", "AMFI monthly aggregates"),
        constraints=("scheme mandates and cash limits",
                     "a prohibition on holding the equivalent of a naked derivative position"),
        instruments=("HK50", "US500"),
        counterparties=("FPIs", "retail redeemers", "promoters selling down stakes"),
        observables=("AMFI monthly SIP inflow", "NSE DII cash activity",
                     "mutual fund cash levels"),
        impact="a calendar-dated, price-insensitive domestic bid that has changed the response "
               "function of Indian equity to foreign selling since about 2020",
        persistence="structural and growing; the flow has not had a down year since 2016, which "
                    "is itself a reason to distrust a cell fitted only on that sample",
        falsifier="two consecutive months of net SIP outflow reported by AMFI"),
    actor(
        "Retail index option traders",
        holds="the majority of weekly index option open interest by contract count, in positions "
              "whose average notional is a fraction of any other major market's",
        forced_to=("close or roll before a weekly expiry because the contract dies",
                   "meet intraday margin on a position sized for premium and not for gamma"),
        when="the expiry afternoon, 09:30-10:00 UTC, while the settlement average is computed",
        information=("broker option chains", "public open-interest snapshots",
                     "an enormous retail commentary ecosystem"),
        constraints=("SEBI position limits and the 2024-25 rationalisation that cut weeklies to "
                     "one per exchange and raised contract sizes",
                     "the peak-margin regime"),
        instruments=("HK50", "US500"),
        counterparties=("proprietary market makers and foreign high-frequency firms, the "
                        "documented other side of the retail loss",),
        observables=("participant-wise open interest by client type",
                     "the India VIX term structure into expiry",
                     "the last-30-minute share of daily volume"),
        impact="concentrates gamma into one afternoon a week, producing the pinning, the terminal "
               "volatility crush and the last-half-hour drift the expiry domain is about",
        persistence="the BEHAVIOUR is persistent; the CALENDAR is not, and it moved twice in ten "
                    "months (November 2024 and September 2025)",
        falsifier="an expiry-day final-30-minute realised volatility no higher than a non-expiry "
                  "day of the same weekday, measured inside a single expiry regime"),
    actor(
        "Bullion importers, nominated agencies and the jewellery trade",
        holds="an import book of 700-900 tonnes of gold a year against essentially zero domestic "
              "mine supply",
        forced_to=("import ahead of festival and wedding seasons because demand is date-driven "
                   "rather than price-driven",
                   "buy dollars to pay for it",
                   "pre-position ahead of an expected customs duty change"),
        when="import clustering in the eight weeks before Dhanteras and Diwali and again before "
             "Akshaya Tritiya; wedding-season restocking November to February",
        information=("their own order books", "duty-change rumours around the Union Budget",
                     "the domestic premium or discount to landed cost"),
        constraints=("the customs duty, cut from 15% to 6% in July 2024",
                     "the tariff rate quota under the UAE trade agreement",
                     "banking channel limits on gold metal loans"),
        instruments=("XAUUSD", "XAGUSD", "USDINR"),
        counterparties=("Swiss and UAE refiners", "Indian households",
                        "the smuggling channel, whose economics the duty cut destroyed"),
        observables=("monthly gold import value in the trade data",
                     "the MCX-versus-London premium in dollars per ounce",
                     "the customs duty notification itself"),
        impact="makes the Indian premium a demand thermometer and the import bill a "
               "current-account item large enough to move USDINR on a monthly horizon",
        persistence="the festival seasonality is millennia old; the DUTY is a policy variable "
                    "that has moved four times in a decade and each move is a regime break",
        falsifier="a Diwali quarter with gold imports below the trailing four-quarter average and "
                  "a negative domestic premium would say the seasonal is gone"),
    actor(
        "The non-resident remittance corridor",
        holds="the world's largest inbound remittance flow, above USD 120bn a year",
        forced_to=("convert to rupees for family maintenance regardless of the rate",
                   "roll or redeem NRI deposits at contractual dates"),
        when="a steady flow with festival and academic-year bumps; deposit rollovers cluster at "
             "one- and three-year anniversaries of a rate-driven inflow surge",
        information=("the rupee's level against its own recent range, which demonstrably "
                     "accelerates opportunistic conversion",
                     "NRE and FCNR(B) deposit rate boards"),
        constraints=("the RBI's ceiling on FCNR(B) and NRE deposit rates, relaxed in depreciation "
                     "episodes as an explicit inflow tool",),
        instruments=("USDINR",),
        counterparties=("Indian banks' NRI desks", "money transfer operators",
                        "the RBI as the ultimate absorber"),
        observables=("private transfers in the balance of payments",
                     "NRI deposit outstanding in the monthly Bulletin",
                     "World Bank remittance estimates"),
        impact="a large, stable, price-OPPORTUNISTIC inflow that leans against depreciation and "
               "is one reason INR downside moves are truncated rather than trending",
        persistence="structural with a documented level-dependence: conversion accelerates when "
                    "the rupee is weak, which is itself a stabiliser and a source of asymmetry",
        falsifier="a depreciation episode of more than 3% in a quarter with no increase in "
                  "private transfer receipts in the balance of payments"),
    actor(
        "Information technology and business services exporters",
        holds="dollar receivables against a rupee cost base, hedged one to four quarters forward",
        forced_to=("sell dollars forward on a rolling board-mandated programme",
                   "roll hedges at quarter end"),
        when="hedge additions cluster at quarter end and at the start of the financial year in "
             "April",
        information=("their own revenue guidance",
                     "the forward premium, which is their hedging revenue"),
        constraints=("accounting hedge-effectiveness rules",
                     "board-mandated minimum hedge ratios"),
        instruments=("USDINR",),
        counterparties=("bank corporate FX desks, who pass the risk into the interbank forward "
                        "market and ultimately into the RBI's forward book",),
        observables=("the USDINR forward premium curve",
                     "quarterly hedge disclosures in company filings",
                     "the RBI's net forward position"),
        impact="the structural forward-market SELLER of dollars, which caps the forward premium "
               "and therefore interacts directly with the swap this desk pays to hold USDINR",
        persistence="structural; the hedge RATIO is countercyclical, falling when the rupee looks "
                    "pinned, which is precisely when it should not",
        falsifier="a quarter in which the one-year forward premium widens above covered interest "
                  "parity while exporters report raising hedge ratios"),
    actor(
        "The MCX-London bullion arbitrage complex",
        holds="a basis position between MCX gold futures and loco-London metal, financed in "
              "rupees and carried against the customs duty",
        forced_to=("close the basis when the domestic premium exceeds the cost of importing",
                   "re-price the entire book the day a duty notification lands"),
        when="the MCX evening session, 13:00-18:00 UTC, when COMEX and MCX trade together",
        information=("the landed cost calculation", "duty rumours",
                     "customs clearance times at the bonded warehouses"),
        constraints=("import licensing through nominated agencies",
                     "the duty itself, which is the dominant term in the basis"),
        instruments=("XAUUSD", "XAGUSD", "USDINR"),
        counterparties=("bullion banks", "jewellers", "the domestic recycling channel"),
        observables=("MCX settlement divided by USDINR against XAUUSD",
                     "the published premium or discount to the official landed price"),
        impact="converts physical Indian demand into a measurable number and gives the desk a "
               "gold demand observable independent of ETF flows and of the COT report",
        persistence="the arbitrage persists; its SIGN is regime-dependent on the duty, so a "
                    "long-sample mean of the premium describes no regime at all",
        falsifier="a month in which the computed premium and reported physical demand move in "
                  "opposite directions"),
    actor(
        "The Government of India market borrowing programme",
        holds="gross market borrowing above INR 14 trillion a year, issued on a published "
              "half-yearly calendar",
        forced_to=("issue to the calendar regardless of the level of yields",
                   "fund the deficit announced on 1 February"),
        when="G-Sec auctions on Friday and T-bill auctions on Wednesday, both around 05:00 UTC",
        information=("its own cash position", "advance tax and GST receipts as they arrive"),
        constraints=("the FRBM deficit glide path",
                     "the RBI's dual role as debt manager and inflation targeter"),
        instruments=("UST10Y", "USDINR"),
        counterparties=("primary dealers who are obliged to bid",
                        "insurance and pension funds", "FAR-route foreign index money"),
        observables=("the auction calendar and its devolvement",
                     "the cut-off yield against the previous close",
                     "the Centre's cash balance in the WSS"),
        impact="supply is date-known, so the tradable event is a DEVOLVEMENT on primary dealers "
               "or a partial acceptance, never the auction itself",
        persistence="permanent; the calendar's predictability is the whole point of it",
        falsifier="a quarter of auctions with no devolvement in which the 10-year still cheapens "
                  "into every Friday"),
    actor(
        "Corporate India's statutory tax and GST calendar",
        holds="the working-capital position of the entire formal economy",
        forced_to=("pay advance tax on 15 June, 15 September, 15 December and 15 March",
                   "file and pay GST by the 20th of each month",
                   "meet quarter-end balance sheet requirements"),
        when="liquidity drains on those exact dates and returns as government spending over the "
             "following fortnight",
        information=("their own tax computations", "the GST portal's deadlines"),
        constraints=("statutory deadlines carrying interest penalties",
                     "no ability to defer without cost"),
        instruments=("USDINR",),
        counterparties=("the Centre's cash balance with the RBI",
                        "banks that must fund the drain in the money market"),
        observables=("overnight TREPS and call rates against the repo rate",
                     "the size of the RBI's variable rate repo auctions",
                     "monthly GST collections published on the 1st"),
        impact="a predictable, dated squeeze in overnight rupee liquidity that reaches FX through "
               "the forward premium, and therefore reaches this desk through the swap",
        persistence="statutory and permanent; the magnitude grew with GST formalisation",
        falsifier="an advance-tax date on which overnight rates do not rise against the preceding "
                  "five-day average, measured across a full year of dates"),
    actor(
        "Farmers, the minimum support price and the procurement machinery",
        holds="the kharif and rabi crop, against an administratively set price floor",
        forced_to=("sell at harvest because storage and credit are scarce",
                   "plant according to the previous season's realised price"),
        when="kharif sowing June-July and harvest October-November; rabi sowing "
             "November-December and harvest March-April",
        information=("the IMD forecast", "the announced MSP", "last season's mandi prices"),
        constraints=("monsoon rainfall", "the MSP itself",
                     "state procurement limits and storage capacity"),
        instruments=("WHEAT", "CORN", "SUGAR", "COTTON", "SOYBEAN"),
        counterparties=("the Food Corporation of India", "private traders", "exporters"),
        observables=("weekly sowing area", "IMD rainfall departure", "mandi arrival data",
                     "the CPI food sub-index"),
        impact="the dominant driver of the 46%-weighted food component of CPI and therefore of "
               "the MPC's reaction function on a two-to-five month lag",
        persistence="structural, with a slow decline in rainfall sensitivity as irrigation "
                    "coverage rises -- a genuine trend that a long-sample cell will mis-fit as a "
                    "stable coefficient",
        falsifier="a season with a rainfall departure worse than -10% and no rise in the CPI food "
                  "sub-index over the following two quarters"),
    actor(
        "Agricultural export policy makers",
        holds="the authority to ban, quota or tax rice, wheat, sugar and onion exports with "
              "immediate effect and no consultation",
        forced_to=("act on domestic food price inflation before an election",
                   "reverse the restriction once the domestic price falls"),
        when="announcements land without warning, typically as an evening notification",
        information=("daily retail prices published by the consumer affairs ministry",
                     "the electoral calendar"),
        constraints=("WTO commitments honoured loosely",
                     "the trade-off between farmer income and consumer prices"),
        instruments=("SUGAR", "SUGARRAW", "WHEAT", "CORN"),
        counterparties=("importing countries, above all in Africa and Southeast Asia",
                        "domestic millers and exporters"),
        observables=("the DGFT notification itself",
                     "the world price reaction within one session",
                     "the daily retail price series that triggers it"),
        impact="India is large enough in rice and sugar that a restriction is a world supply "
               "shock; the 2023 rice export ban and its 2024 relaxation are the cleanest recent "
               "examples and both are dated to the day",
        persistence="episodic but recurrent: at least one restriction every two years since 2007",
        falsifier="a DGFT export restriction on sugar or rice with no move in the corresponding "
                  "world price within two sessions"),
    actor(
        "Proprietary and foreign high-frequency market makers",
        holds="the short-gamma book against retail on expiry day, and the cash-futures basis",
        forced_to=("hedge dynamically into the settlement window",
                   "maintain quotes under exchange market-making obligations"),
        when="throughout the session, with the largest hedging demand in the final 30 minutes of "
             "an expiry day",
        information=("full order-book depth", "their own flow",
                     "co-located latency to both exchanges"),
        constraints=("SEBI's algorithmic trading and co-location rules", "position limits",
                     "the 2025 enforcement action against manipulative expiry strategies"),
        instruments=("HK50", "US500"),
        counterparties=("retail option buyers", "index arbitrageurs",
                        "the clearing corporation"),
        observables=("the Pro category in participant-wise open interest",
                     "the cash-futures basis into expiry",
                     "the last-30-minute share of daily volume"),
        impact="converts retail's option position into mechanical hedging flow in the underlying, "
               "which is the channel from the options market to the index and from there to the "
               "risk-appetite leg of USDINR",
        persistence="persistent as a class; individual participants have been removed by "
                    "enforcement, which is a live regime risk for any expiry-day cell",
        falsifier="an expiry day on which the Pro net option position is flat and the "
                  "last-30-minute volume share sits at its non-expiry median"),
)

# --------------------------------------------------------------------------- the domains
DOMAINS: tuple[dict[str, Any], ...] = (
    domain("IN-A", "RBI policy events and the managed-volatility reaction function",
           objects=("the six MPC resolutions a year at 04:30 UTC",
                    "the governor's statement and the 06:30 UTC press conference",
                    "the minutes 14 days later, with their dissent count",
                    "off-cycle resolutions",
                    "the stance language, which has moved the market more than the rate"),
           conditions=("the policy era",
                       "whether the decision is a surprise against the OIS-implied path",
                       "the liquidity position, surplus or deficit",
                       "whether CPI is inside or outside the tolerance band"),
           instruments=("USDINR", "UST10Y", "HK50"),
           controls=("the same statistic on the six nearest NON-MPC days of the same weekday, "
                     "separating the event from the weekday",
                     "the same statistic on USDCNH on the same dates, separating India from an "
                     "EM Asia move",
                     "the same statistic on USDINR on FOMC days, separating a domestic reaction "
                     "from a dollar reaction",
                     "a placebo list of RBI press releases that are not resolutions"),
           notes="the minutes release is a SECOND event with its own reaction and is routinely "
                 "ignored as fourteen days stale; it is not stale to a dissent count"),
    domain("IN-B", "The FBIL reference-rate window and intervention microstructure",
           objects=("the 06:30-07:00 UTC random-minute fixing window",
                    "the 08:00 UTC publication", "the cash, tom and spot ladder",
                    "the onshore-offshore NDF basis"),
           conditions=("month end and quarter end",
                       "days on which the RBI is visibly supplying dollars",
                       "the size of the preceding day's FPI flow"),
           instruments=("USDINR", "USDCNH"),
           controls=("the same window measured on USDCNH, which has its own fix at a different "
                     "time and cannot share the mechanism",
                     "the same half hour on a day with no fixing, such as a mid-week bank holiday",
                     "a random half hour drawn from the same session, to show the effect is in "
                     "THIS window and not merely in the session",
                     "the same statistic before and after the 2018 move from an RBI-computed to "
                     "an FBIL-computed fix"),
           notes="the random-minute design predicts DIFFUSION of flow across the window rather "
                 "than a spike, which is the opposite prediction to the London 16:00 fix "
                 "literature and is what makes this a genuine test rather than a transplant"),
    domain("IN-C", "Index expiry mechanics across three calendars",
           objects=("weekly index option expiry",
                    "the last-30-minute settlement average, 09:30-10:00 UTC",
                    "the monthly last-Tuesday expiry",
                    "the volatility crush into and after settlement"),
           conditions=("WHICH expiry regime: Thursday to 2024-11-19, single weekly Thursday to "
                       "2025-08-28, Tuesday from 2025-09-02",
                       "open interest relative to its trailing median",
                       "proximity of the index to a large strike"),
           instruments=("HK50", "US500", "USDINR"),
           controls=("the same statistic on the weekday the expiry USED to fall on, measured "
                     "AFTER the move -- the sharpest control in this pack",
                     "the same statistic on a Hong Kong or Japanese index on the same dates",
                     "the same statistic on BSE's expiry day, now a different weekday",
                     "a pre-November-2024 sample, where four weeklies existed and the "
                     "concentration hypothesis predicts a weaker effect"),
           notes="September 2025 is a natural experiment: if the effect followed the expiry to "
                 "Tuesday it is an expiry effect; if it stayed on Thursday it was a weekday "
                 "artefact all along, and the whole domain dies honestly"),
    domain("IN-D", "Foreign and domestic institutional flow response",
           objects=("daily FPI equity and debt net", "daily DII cash activity",
                    "FII net index futures position", "the FPI-minus-DII difference"),
           conditions=("the sign and size of the preceding day's global EM flow",
                       "index inclusion or exclusion events",
                       "whether the domestic SIP flow is at a monthly deployment date"),
           instruments=("USDINR", "HK50", "CHINAH"),
           controls=("the same regression on Korean and Taiwanese foreign flow, which share the "
                     "EM factor and not the Indian mechanism",
                     "a lead-lag reversal: if flow predicts price, price must not predict flow at "
                     "the same lag",
                     "a same-day versus next-day split, since the print lands after the close"),
           notes="the publication time IS the point-in-time problem: a cell that trades the flow "
                 "on the day it describes is trading a number published after that day's close"),
    domain("IN-E", "Gold import seasonality, the duty regime and the domestic premium",
           objects=("the eight weeks before Dhanteras and Diwali", "Akshaya Tritiya",
                    "the November-February wedding season", "customs duty notifications",
                    "the MCX-versus-London premium"),
           conditions=("the duty rate in force",
                       "whether the domestic market is at a premium or a discount",
                       "the rupee's own trend, which moves the landed cost"),
           instruments=("XAUUSD", "XAGUSD", "USDINR"),
           controls=("the same calendar window in years when the festival fell in a different "
                     "Gregorian month, which separates the FESTIVAL from October",
                     "the same statistic on XAGUSD, where Indian demand is a smaller share",
                     "the same statistic in Chinese New Year windows, separating Indian demand "
                     "from generic Asian physical demand",
                     "a pre- and post-July-2024 split on the duty cut"),
           notes="the festival dates move by weeks in the Gregorian calendar, which makes the "
                 "control for 'is this October or is this Diwali' free"),
    domain("IN-F", "The crude import bill and the oil-company dollar bid",
           objects=("monthly crude import volume and value", "the Russian discount",
                    "retail fuel price freezes", "the daily dollar purchase programme"),
           conditions=("the level of Brent", "whether an election is within six months",
                       "whether the RBI is supplying dollars through a special window"),
           instruments=("USDINR", "XBRUSD", "XTIUSD"),
           controls=("the same relationship for another large net oil importer's currency, which "
                     "shares the oil exposure and not the RBI",
                     "months in which the deficit widened on gold rather than crude",
                     "a placebo using refined product EXPORTS, which run the other way"),
           notes="India is a large crude importer AND a large refined-product exporter, so the "
                 "net oil balance is much smaller than the gross import bill; a cell built on "
                 "gross imports is measuring the wrong number"),
    domain("IN-G", "Monsoon, sowing and the food component of CPI",
           objects=("the IMD long-range forecast in April and May",
                    "onset over Kerala around 1 June", "daily and weekly rainfall departure",
                    "weekly kharif and rabi sowing area",
                    "the CPI food sub-index on the 12th"),
           conditions=("El Nino or La Nina state", "weekly reservoir storage",
                       "the MSP announced for the season"),
           instruments=("SUGAR", "COTTON", "SOYBEAN", "CORN", "WHEAT", "USDINR"),
           controls=("the same rainfall-to-price relationship for a crop India does not export, "
                     "isolating the domestic channel from the world price",
                     "Thai and Brazilian weather on the same commodities and dates",
                     "an irrigation-coverage split: the sensitivity should be FALLING, and a "
                     "stable coefficient across twenty years is evidence of over-fitting"),
           notes="the one domain where a free, daily, gridded physical input predicts a monthly "
                 "policy-relevant print at a two-to-five month lag"),
    domain("IN-H", "The fiscal and tax-payment liquidity calendar",
           objects=("advance tax on 15 June, 15 September, 15 December and 15 March",
                    "GST payment by the 20th",
                    "the Union Budget on 1 February at 05:30 UTC",
                    "the half-yearly borrowing calendar",
                    "monthly GST collections on the 1st"),
           conditions=("whether system liquidity is in surplus or deficit",
                       "the size of the Centre's cash balance",
                       "whether the RBI is running VRR or VRRR auctions"),
           instruments=("USDINR", "UST10Y"),
           controls=("the same statistic on the 14th and the 16th, to show the effect is ON the "
                     "statutory date",
                     "years in which the date fell on a weekend and payment shifted",
                     "Indonesian and Philippine tax dates, which share the concept and not the "
                     "calendar"),
           notes="transmission to a USDINR CFD runs through the FORWARD PREMIUM and therefore "
                 "through the swap this desk pays, not through spot"),
    domain("IN-I", "Month end, quarter end and the forward book",
           objects=("exporter hedge rolls at quarter end",
                    "importer payment clustering at month end",
                    "the RBI's own buy-sell swap maturities", "the forward premium curve"),
           conditions=("the 31 March financial year boundary, unique to India in this region",
                       "whether the forward premium is above or below covered interest parity"),
           instruments=("USDINR",),
           controls=("the same statistic at the CALENDAR year end, which is not India's fiscal "
                     "year end and should be weaker if the mechanism is fiscal",
                     "USDSGD and USDTHB at their own month ends",
                     "a maturity-bucket placebo using tenors no corporate hedges"),
           notes="the 31 March boundary is the cleanest India-specific calendar control available "
                 "anywhere in this pack: no other country in this region shares it"),
    domain("IN-J", "Bond index inclusion and the FAR-route flow",
           objects=("the JPMorgan GBI-EM phase-in from June 2024",
                    "the Bloomberg EM local inclusion from January 2025",
                    "the FTSE Russell inclusion", "monthly index rebalance dates"),
           conditions=("whether the date is a phase-in step or a routine rebalance",
                       "the level of the spread to UST10Y",
                       "the size of that month's G-Sec supply"),
           instruments=("UST10Y", "USDINR"),
           controls=("the same event study on the 2020-21 Chinese index inclusions, where the "
                     "mechanism is identical and the country is not",
                     "an announcement-versus-implementation split, since an efficient market "
                     "prices the announcement",
                     "a non-FAR security control: the effect must be larger in FAR securities"),
           notes="the phase-in is over, so what remains is the ONGOING monthly rebalance and the "
                 "behaviour of an index holder base in a sell-off, not the inclusion event"),
    domain("IN-K", "Remittances, NRI deposits and the inflow reaction function",
           objects=("private transfer receipts in the balance of payments",
                    "NRE and FCNR(B) deposit outstanding",
                    "the RBI's episodic relaxation of deposit rate ceilings"),
           conditions=("whether the rupee is more than one standard deviation weak against its "
                       "own three-month range",
                       "whether a special deposit window is open"),
           instruments=("USDINR",),
           controls=("the same relationship for the Philippine peso, the other large remittance "
                     "recipient in this region, which shares the mechanism and not the RBI",
                     "a placebo using tourism receipts, a services inflow with no level "
                     "opportunism"),
           notes="the level-opportunism claim -- that conversion accelerates when the rupee is "
                 "weak -- is the testable part; the flow's SIZE is not news to anyone"),
    domain("IN-L", "Agricultural export policy shocks",
           objects=("DGFT notifications banning, quotaing or taxing rice, sugar, wheat or onion "
                    "exports",
                    "the relaxation notifications that follow",
                    "the daily retail price series that triggers them"),
           conditions=("the domestic retail price against its year-ago level",
                       "proximity to a state or general election",
                       "the size of the FCI buffer stock"),
           instruments=("SUGAR", "SUGARRAW", "WHEAT", "CORN"),
           controls=("the same event study on Vietnamese and Thai export policy announcements, "
                     "which move the same commodities through a different government",
                     "a placebo list of DGFT notifications on commodities where India is small",
                     "the same statistic on the day BEFORE the notification, to test for leakage"),
           notes="the leakage test matters more here than anywhere else in this pack: these "
                 "notifications have a history of moving the market before publication"),
    domain("IN-M", "Session handover and the direction-dependent cost of USDINR",
           objects=("the 03:30-11:30 UTC onshore window",
                    "the NDF's continuation after the onshore close",
                    "the 37-point median spread and the -480.08 / -42.45 swap asymmetry",
                    "the overlap with the London open at 07:00 UTC"),
           conditions=("whether the onshore market is open",
                       "the direction of the position, because the carry is eleven times more "
                       "expensive long than short",
                       "Indian exchange holidays, when only the NDF trades"),
           instruments=("USDINR", "USDCNH", "USDX"),
           controls=("the same statistic on USDCNH, which has an onshore-offshore split of the "
                     "same shape under a different central bank",
                     "a cost-stripped and a cost-charged version of every edge, because an INR "
                     "cell that survives gross and dies net is the normal outcome here",
                     "the same statistic on Indian exchange holidays"),
           notes="this domain exists to keep the cost honest. A USDINR cell reported without the "
                 "registry swap charged BY DIRECTION is not a result"),
)

# --------------------------------------------------------------------------- miners (specs)
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("in_mpc_event_study", domain_ids=("IN-A",), kind="event",
          entry="research.countries.ind.miners:mpc_event_study", cadence_s=86400.0,
          steerable=False,
          notes="SPEC, NOT YET WIRED. Reads CENTRAL_BANK['dates'], USDINR and UST10Y H1 bars, "
                "and runs all four IN-A controls. Refuses a verdict when the OIS-implied path is "
                "unavailable rather than treating every resolution as a surprise"),
    miner("in_fix_window_flow", domain_ids=("IN-B",), kind="microstructure",
          entry="research.countries.ind.miners:fix_window_flow", cadence_s=3600.0,
          notes="SPEC, NOT YET WIRED. Tests DIFFUSION across 06:30-07:00 UTC rather than a spike, "
                "because the random-minute design predicts diffusion"),
    miner("in_expiry_regime_split", domain_ids=("IN-C",), kind="calendar",
          entry="research.countries.ind.miners:expiry_regime_split", cadence_s=86400.0,
          steerable=False,
          notes="SPEC, NOT YET WIRED. The September 2025 natural experiment; reports the weekday "
                "control before it reports the effect"),
    miner("in_flow_response", domain_ids=("IN-D", "IN-J"), kind="flow",
          entry="research.countries.ind.miners:flow_response", cadence_s=86400.0,
          notes="SPEC, NOT YET WIRED. Next-day only; the same-day version is a look-ahead and is "
                "refused rather than flagged"),
    miner("in_gold_premium", domain_ids=("IN-E",), kind="basis",
          entry="research.countries.ind.miners:gold_premium", cadence_s=86400.0,
          notes="SPEC, NOT YET WIRED. Publishes the premium in dollars per ounce with the duty "
                "regime label on every row, so no row is comparable across a duty change by "
                "accident"),
    miner("in_monsoon_food_lag", domain_ids=("IN-G",), kind="macro",
          entry="research.countries.ind.miners:monsoon_food_lag", cadence_s=604800.0,
          notes="SPEC, NOT YET WIRED. Fits the lag rather than assuming it and reports the "
                "irrigation-trend control alongside"),
    miner("in_tax_liquidity_calendar", domain_ids=("IN-H", "IN-I"), kind="calendar",
          entry="research.countries.ind.miners:tax_liquidity_calendar", cadence_s=86400.0,
          steerable=False,
          notes="SPEC, NOT YET WIRED. The 14th and 16th placebo is computed before the 15th is "
                "reported"),
    miner("in_export_policy_shock", domain_ids=("IN-L",), kind="event",
          entry="research.countries.ind.miners:export_policy_shock", cadence_s=3600.0,
          notes="SPEC, NOT YET WIRED. Runs the day-before leakage test as a first-class output "
                "rather than as a diagnostic"),
    miner("in_cost_honesty", domain_ids=("IN-M",), kind="cost",
          entry="research.countries.ind.miners:cost_honesty", cadence_s=3600.0, steerable=False,
          notes="SPEC, NOT YET WIRED. Charges the registry swap by direction on every USDINR "
                "candidate and fails one that survives only gross"),
)

# --------------------------------------------------------------------------- transmission seeds
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("IN-E01", source="RBI MPC resolution surprise against the OIS path",
         mechanism="a hawkish surprise raises the carry and signals a higher tolerance for rupee "
                   "strength, so USDINR falls and the local curve reprices",
         targets=("USDINR", "UST10Y"), sign="-", horizon="0 to 3 sessions",
         lag="0 -- the resolution is public at 04:30 UTC",
         control="the same statistic on USDCNH on the same dates",
         notes="FALSIFIER: no measurable difference between hawkish-surprise and "
               "dovish-surprise days across a full era"),
    edge("IN-E02", source="Indian monthly gold import value",
         mechanism="India is a marginal price setter in physical gold; an import surge is demand "
                   "that London must source, and it arrives as a dated monthly print",
         targets=("XAUUSD", "XAGUSD"), sign="+", horizon="1 to 3 months",
         lag="15 days -- the trade print lands around the 15th of the following month",
         control="the same relationship against the Shanghai premium, which carries Chinese "
                 "demand through the identical channel",
         notes="FALSIFIER: an import surge quarter with a FALLING domestic premium and no XAUUSD "
               "response. Duty regime must be held fixed inside the window"),
    edge("IN-E03", source="Indian gold import value",
         mechanism="gold is the second-largest import line; a surge widens the trade deficit and "
                   "the rupee weakens",
         targets=("USDINR",), sign="+", horizon="1 to 2 months from the trade print",
         lag="15 days",
         control="months in which the deficit widened on CRUDE instead, which must show the same "
                 "sign if the mechanism is the deficit rather than gold specifically",
         notes="FALSIFIER: a record gold import month with a narrowing trade deficit and a "
               "stronger rupee"),
    edge("IN-E04", source="Indian crude import volume",
         mechanism="the third-largest crude importer with short-run price-inelastic demand; "
                   "import volume growth is a demand signal for the world balance",
         targets=("XBRUSD", "XTIUSD"), sign="+", horizon="1 month", lag="15 days",
         control="Chinese crude import volume, the larger buyer, on the same dates",
         notes="FALSIFIER: two consecutive quarters of rising Indian import volume with falling "
               "Brent and no supply-side explanation"),
    edge("IN-E05", source="DGFT sugar export restriction or quota",
         mechanism="a top-two producer and swing exporter removing supply from the world balance "
                   "by notification, with no notice",
         targets=("SUGAR", "SUGARRAW"), sign="+", horizon="0 to 5 sessions",
         lag="0 -- the notification is the event",
         control="Thai and Brazilian policy announcements on the same commodity, plus the "
                 "white-versus-raw differential, which must move if the mechanism is Indian "
                 "refined supply rather than world supply",
         notes="FALSIFIER: an export restriction with no move in SUGAR within two sessions. Run "
               "the day-before leakage test first"),
    edge("IN-E06", source="Indian monsoon rainfall departure, June to September",
         mechanism="the world's largest cotton area is largely rain-fed in Maharashtra and "
                   "Gujarat, so a good monsoon raises expected supply",
         targets=("COTTON",), sign="-", horizon="1 to 4 months", lag="1 day on the IMD grid",
         control="US and Brazilian weather on the same dates, and a Chinese reserve-auction check",
         notes="FALSIFIER: a season with a departure above +10% and a rising world price with no "
               "offsetting supply event elsewhere"),
    edge("IN-E07", source="NSE FII net index futures position",
         mechanism="the same foreign investor base expresses EM Asia risk appetite across India "
                   "and Hong Kong, so the Indian print is a same-factor observable published "
                   "free and daily when most of the region publishes nothing",
         targets=("HK50", "CHINAH"), sign="+", horizon="1 to 5 sessions",
         lag="1 session -- the print lands after the Indian close",
         control="Korean and Taiwanese foreign flow, which carry the EM factor without India",
         notes="FALSIFIER: no incremental predictive content once Korean and Taiwanese flow are "
               "in the regression"),
    edge("IN-E08", source="NSE FII cash net selling",
         mechanism="equity outflow must be converted, so sustained foreign selling is a "
                   "mechanical dollar bid",
         targets=("USDINR",), sign="+", horizon="1 to 10 sessions", lag="1 session",
         control="the same statistic on days the RBI is visibly supplying dollars, when the "
                 "mechanism is deliberately blocked and the effect must weaken",
         notes="FALSIFIER: a month of heavy FII selling with USDINR falling and reserves flat"),
    edge("IN-E09", source="Indian advance-tax statutory dates",
         mechanism="a dated rupee liquidity drain widens the forward premium, raising the cost of "
                   "carrying a short-dollar position and mechanically favouring the dollar",
         targets=("USDINR",), sign="+", horizon="0 to 3 sessions around the four dates",
         lag="0 -- the dates are statutory and known years ahead",
         control="the 14th and the 16th of the same months, and years when the date fell on a "
                 "weekend",
         notes="FALSIFIER: no difference in the forward premium between statutory dates and "
               "surrounding days across a full year. Requires system liquidity in deficit"),
    edge("IN-E10", source="Indian CPI food surprise",
         mechanism="an upside food surprise delays the RBI, narrowing the expected India-US "
                   "spread and reaching the global EM local-rates complex",
         targets=("UST10Y", "USDINR"), sign="-", horizon="0 to 2 sessions",
         lag="12 days -- CPI lands on the 12th at 10:30 UTC",
         control="Indonesian and Philippine CPI dates, which share the mechanism and not the "
                 "monsoon",
         notes="FALSIFIER: an Indian CPI surprise above 50bp with no EM rates reaction at all. "
               "Exclude days carrying a US CPI print"),
    edge("IN-E11", source="USDINR realised volatility regime break",
         mechanism="both India and China run managed EM Asia currencies whose central banks "
                   "respond to the dollar; a break in Indian managed volatility signals a change "
                   "in the regional tolerance for depreciation",
         targets=("USDCNH", "USDX"), sign="+", horizon="5 to 20 sessions",
         lag="0 -- computable from price",
         control="residualise USDX out first; the claim is about the RESIDUAL co-movement",
         notes="FALSIFIER: no residual co-movement once the dollar factor is removed"),
    edge("IN-E12", source="Indian index expiry afternoon",
         mechanism="THE NULL EDGE, stated deliberately. Indian expiry hedging flow should NOT "
                   "reach the US session, so a measurable effect is the sharpest available "
                   "evidence that the expiry statistic is a global-risk artefact",
         targets=("US500",), sign="0", horizon="same session", lag="0",
         control="the same statistic on non-expiry days of the same weekday",
         notes="FALSIFIER: a stable, measurable US500 response to Indian expiry, which would "
               "falsify the whole expiry domain rather than confirm it. A null edge that fires is "
               "the most informative outcome in this pack"),
    edge("IN-E13", source="MCX-versus-London gold premium",
         mechanism="a positive domestic premium means physical demand exceeds import supply, "
                   "which must ultimately be met from the London market",
         targets=("XAUUSD", "USDINR"), sign="+", horizon="5 to 20 sessions",
         lag="0 -- computable from the daily bhavcopy and the fix",
         control="the Shanghai premium, which carries Chinese demand through the same channel",
         notes="FALSIFIER: a sustained Indian premium with no change in London lease rates or "
               "price. No duty change may fall inside the window"),
    edge("IN-E14", source="Indian infrastructure capex cycle and the budget capital outlay",
         mechanism="a budget capital outlay that is actually spent raises imported metal demand, "
                   "and India is a growing marginal buyer of refined copper",
         targets=("XCUUSD",), sign="+", horizon="1 to 3 quarters",
         lag="0 at the budget, then monthly on the controller-general's expenditure data",
         control="Chinese grid capex on the same dates, which dominates the copper balance and "
                 "must be residualised before any Indian claim is made",
         notes="FALSIFIER: no residual copper response once Chinese demand is controlled for -- "
               "which is the likely outcome and is worth measuring once rather than assuming"),
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    era("IN-R1", start="2010-01-01", end="2016-06-30",
        label="pre-inflation-targeting managed float",
        what_changed="no formal target, heavy discretionary intervention, the 2013 taper-tantrum "
                     "crisis and the FCNR(B) swap window that ended it",
        invalidates="USDINR volatility in this era is not comparable to anything after it; a "
                    "variance statistic pooled across 2013 is describing a crisis",
        notes="markers: the 2013 depreciation through 68, the FCNR(B) swap raising about USD 34bn"),
    era("IN-R2", start="2016-07-01", end="2020-02-29",
        label="flexible inflation targeting under Patel and Das",
        what_changed="a 4% CPI target with a band and a statutory MPC, plus two domestic "
                     "structural shocks with no analogue anywhere: demonetisation in November "
                     "2016 and the GST transition in July 2017",
        invalidates="any liquidity, cash-demand or activity-nowcast cell fitted on 2016-2018 is "
                    "fitted on two one-off shocks",
        notes="markers: 2016-11-08 demonetisation, 2017-07-01 GST"),
    era("IN-R3", start="2020-03-01", end="2021-12-31",
        label="pandemic, reserve accumulation and the retail derivatives boom",
        what_changed="record reserve accumulation past USD 600bn, an unusually pinned policy "
                     "rate, an exceptional liquidity surplus, and the beginning of the retail "
                     "options boom that now defines the expiry domain",
        invalidates="realised USDINR volatility reached historic lows; a variance-conditioned "
                    "cell fitted here will not generalise to any other era",
        notes="markers: reserves crossing USD 600bn, the retail trading account surge"),
    era("IN-R4", start="2022-01-01", end="2024-12-10",
        label="tightening, the 83 defence and the Das plateau",
        what_changed="aggressive smoothing around 83, four weekly expiries collapsing to one on "
                     "2024-11-20, the GBI-EM phase-in from 2024-06-28, and the gold duty cut from "
                     "15% to 6% on 2024-07-23",
        invalidates="the most pinned USDINR regime on record and therefore the most misleading "
                    "sample a breakout or range cell can be fitted on",
        notes="three separate market-design changes land inside one era; a cell spanning it must "
              "say which of them it is claiming to be about"),
    era("IN-R5", start="2024-12-11", end="2025-08-31",
        label="the Malhotra transition and the step re-pricing",
        what_changed="a governor change followed by a rapid repricing of the rupee from the low "
                     "84s through 87, easing from February 2025, and a visibly wider tolerance "
                     "for depreciation",
        invalidates="the sharpest break in the managed-volatility series in a decade; anything "
                    "fitted on IN-R4 and evaluated here is measuring the break, not the edge",
        notes="this era is the reason the era table is cut at GOVERNORS and not at years"),
    era("IN-R6", start="2025-09-01", end=None,
        label="the Tuesday-expiry and tariff era",
        what_changed="NSE expiry on Tuesday and BSE on Thursday from 2025-09-01, US tariff "
                     "pressure on Indian exports, and a rupee trading materially weaker than the "
                     "2022-2024 plateau",
        invalidates="every expiry cell must be re-fitted inside this era; the pre-September "
                    "sample is a CONTROL, never training data",
        notes="the current regime, and the one a live candidate is actually trading"),
)


# --------------------------------------------------------------------------- assembly
MISSION = (
    "mine India to exhaustion for gauntlet-ready candidates on the four mechanisms no other "
    "country in this region has all of: a central bank that manages realised volatility as "
    "policy, the world's largest options book on a calendar that moved twice in ten months, a "
    "festival-dated gold import bill large enough to move the current account, and a monsoon "
    "carrying 46% of the CPI basket")
NOTES = (
    "ONE instrument is executable here (USDINR) and it carries a direction-dependent carry: swap "
    "-480.08 long against -42.45 short. Every Indian instrument these domains are about -- NIFTY "
    "and its weeklies, SENSEX, MCX gold, the 10-year G-Sec, the NDF, India VIX -- is ABSENT from "
    "the broker universe and is named in this module's TRANSMISSION_TARGETS with the symbols its "
    "mechanism reaches.")


def fields() -> dict[str, Any]:
    """The LOSSLESS form of this pack: the twenty-one mandate fields plus the two this pack adds,
    as a plain mapping in `research.countries` row shape.

    This exists because two sibling frameworks landed with DIFFERENT row schemas.
    `research.countries` builds edges as {id, source, mechanism, targets, sign, horizon, lag,
    control, evidence} and `libs.research.country_lab.CountryPack` coerces whatever it is given
    into its own `TransmissionSeed` / `HolidayRule` / `Era` shapes, which do not carry those
    names. `pack()` returns the coerced object because that is what the framework's consumers
    expect; `fields()` returns the data as written, which is what a validator and a miner in this
    package should read. When the two schemas converge, this function becomes a formality.
    """
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
        "transmission_targets": TRANSMISSION_TARGETS,
        "absent_source_layers": ABSENT_SOURCE_LAYERS,
        "mission": MISSION, "notes": NOTES,
    }


def pack() -> Any:
    """India's pack: `CountryPack` when the framework has landed, else the same fields as a dict.

    `transmission_targets` is passed alongside the twenty-one frozen fields. `build_pack` keeps it
    in the dict form and drops it from the dataclass when the dataclass does not declare it, which
    is the right trade: an absent instrument must be NAMED somewhere, and losing the name is worse
    than carrying one field the container does not know about.
    """
    return build_pack(**fields())
