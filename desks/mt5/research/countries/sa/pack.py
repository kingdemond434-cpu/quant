"""THE SAUDI ARABIA COUNTRY PACK -- the marginal barrel, the petrodollar, and a WEEKLY demand print.

WHY SAUDI ARABIA IS THE ANCHOR OF THIS CIVILIZATION AND NOT A KOREA WITH SAND. Korea is carried by
a customs print; Japan by a fixing and a settlement day. Saudi Arabia is carried by three things
that exist nowhere else on the desk's map:

  * A PEG THAT EXPORTS US POLICY UNCHANGED. 3.75 riyals to the dollar since June 1986. SAMA keeps
    no rate calendar of its own: it moves with the FOMC, usually within hours. So the Saudi policy
    date list IS the FOMC date list, and a "Saudi rate surprise" is a category error -- unless
    SAMA deviates, and a deviation is itself the peg-stress observable rather than a policy one.
  * A WEEKLY CARD-SPENDING PRINT. SAMA publishes point-of-sale transactions (نقاط البيع) WEEKLY:
    value, count and the merchant-category split. No other major oil exporter publishes household
    demand at that frequency. It is a nowcast of the economy whose fiscal breakeven sets how hard
    OPEC+ has to defend a price, it moves with Ramadan and Eid rather than with the quarter, and
    its own seasonality is a Hijri one that no Gregorian dummy can absorb.
  * THE MARGINAL BARREL, DECIDED ADMINISTRATIVELY. Production is a quota and a policy choice, the
    official selling prices to Asia are announced around the fifth of each month, and both are
    announcements with timestamps rather than market outcomes. That makes them EVENTS, which is
    the shape this desk can actually test.

WHAT THIS PACK MAY NOT DO. The riyal is not on the broker's tape: USDSAR is named in
`ABSENT_INSTRUMENTS`, never in `executable_instruments`, and the peg's economics route into crude,
gold, the dollar index and global risk through `TRANSMISSION_EDGES_SEED`. The national oil company
and the listed banks enter as SECTOR OBSERVABLES only -- their names appear in `TERMINOLOGY` so an
Arabic-language miner recognises the words, and never as a symbol on a docket (two-lane order,
2026-09-06). No crypto-exchange ground is hunted anywhere here (mandate 2026-08-18).

WHAT IS EXECUTABLE. Crude (XTIUSD, XBRUSD), gas (XNGUSD), gold and silver, the dollar index, the
US majors and the two Treasury futures. Every Saudi mechanism in this file terminates in one of
them, because those are the prices the box can actually put an order into.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from typing import Any

from countries import (
    DATASET_FIELDS,
    actor,
    build_pack,
    dataset,
    domain,
    edge,
    era,
    holiday_table,
    miner,
    resolve,
    source_class,
)

CODE = "sa"
NAME = "Saudi Arabia"
REGION_COMMAND = "MIDDLE_EAST"
CURRENCY = "SAR"
NATIVE_LANGUAGES = ("ar",)

#: Arabic, as Unicode sees it: the base block, the supplement, the extended-A block and the two
#: presentation-forms blocks a copy-paste from a Gulf newspaper or a PDF often carries.
#:
#: `countries.has_script` knows han, hangul and kana -- the East Asian packs are what it was
#: written for. Rather than edit a module three other builders are writing into this hour, the
#: Middle East packs carry their own detector and the tests assert on it, so a pack cannot quietly
#: become an English glossary. A miner reading `نقاط البيع` finds nothing if the pack spells it
#: "point of sale".
ARABIC_RANGES: tuple[tuple[int, int], ...] = ((0x0600, 0x06FF), (0x0750, 0x077F),
                                              (0x08A0, 0x08FF), (0xFB50, 0xFDFF),
                                              (0xFE70, 0xFEFF))


def has_arabic(text: str) -> bool:
    """True when `text` carries at least one Arabic codepoint. Reused by the `ae` pack."""
    return any(any(lo <= ord(ch) <= hi for lo, hi in ARABIC_RANGES) for ch in str(text))


def arabic_terms(terminology: dict[str, tuple[str, ...]]) -> list[str]:
    """Every term in a terminology table actually written in Arabic script."""
    return [t for terms in terminology.values() for t in terms if has_arabic(t)]


#: Saudi Arabia's OWN price, on this broker: there is none. The riyal is a policy instrument, not
#: a quote, and an empty tuple here is a measurement rather than an oversight.
OWN_PRICE: tuple[str, ...] = ()

#: What the SA department may place an order in. Every one is in the broker's registry and none is
#: a single-name equity.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "XTIUSD", "XBRUSD", "XNGUSD", "XAUUSD", "XAGUSD", "USDX", "EURUSD", "USDJPY", "USDCAD",
    "USDNOK", "US500", "NAS100", "US30", "UST10Y")

#: The instruments a Gulf desk would reach for that THIS broker does not quote. Named, with what
#: carries them instead: a silently dropped instrument becomes a silently dropped mechanism.
ABSENT_INSTRUMENTS: tuple[dict[str, str], ...] = (
    {"instrument": "USDSAR spot",
     "why": "absent from desks/mt5/data/universe/universe.json; the peg means there is little to "
            "quote -- spot has traded in a few pips around 3.7500 since 1986",
     "carried_by": "nothing directly. Peg stress is read from SAIBOR and 12-month forward points "
                   "as OBSERVABLES and expressed in XAUUSD, USDX and crude, never in the riyal"},
    {"instrument": "USDSAR 12-month forward / NDF points",
     "why": "no forward curve is quoted on this venue at all",
     "carried_by": "public commentary and central-bank statistics only; pit_feasible is False for "
                   "the forward series and the pack says so rather than assuming an archive"},
    {"instrument": "TASI (Tadawul All Share Index) or its MT30 future",
     "why": "no Saudi equity index CFD in the broker registry",
     "carried_by": "XBRUSD for the oil-revenue leg and US500/NAS100 for the global risk leg, with "
                   "the basis stated as a cost rather than assumed away"},
    {"instrument": "Dubai/Oman or Murban crude (the grades Asia actually prices off)",
     "why": "the broker quotes WTI and Brent only",
     "carried_by": "XBRUSD, with the Brent-Dubai EFS named as an UNMEASURED basis; an OSP study "
                   "that treats Brent as the Asian marker is off by that spread"},
    {"instrument": "Saudi government sukuk / USD bonds",
     "why": "no Saudi rates instrument is quoted",
     "carried_by": "UST10Y as the global duration leg; the Saudi credit spread is UNMEASURED by "
                   "name"},
)

#: Where the economics land when the Saudi instrument itself is absent. Read by
#: `instrument_report` and by the Middle East interaction miner.
TRANSMISSION_TARGETS: tuple[str, ...] = ("XBRUSD", "XTIUSD", "XNGUSD", "XAUUSD", "USDX", "US500",
                                         "NAS100", "USDJPY", "UST10Y")


# --------------------------------------------------------------------------- central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Saudi Central Bank (SAMA)",
    "native_name": "البنك المركزي السعودي (ساما)",
    "committee": "the Governor and the Board; there is no published voting committee and no "
                 "minutes -- the decision is a statement, not a vote count",
    "policy_rate": "the repo rate and the reverse repo rate (معدل اتفاقيات إعادة الشراء). The "
                   "reverse repo is the floor the banks actually place cash at and is the one to "
                   "compare with the Fed's IORB.",
    "meetings_per_year": 8,
    "schedule_rule": (
        "SAMA PUBLISHES NO RATE CALENDAR AND DOES NOT NEED ONE. Under the 3.75 peg the riyal's "
        "policy rate is the dollar's, so SAMA moves with the FOMC -- normally a statement the "
        "same evening Riyadh time, within a few hours of the 18:00-18:15 UTC decision. THE SAUDI "
        "DATE LIST IS THEREFORE THE FOMC DATE LIST (eight scheduled FOMC meetings a year), and a "
        "study that treats a SAMA decision as an independent event is measuring the Fed with a "
        "lag and calling it Saudi Arabia. The tradable object is the DEVIATION: a SAMA move that "
        "is not a Fed move, a size that does not match, or a silence where a match was expected."),
    "minutes_rule": "NONE. There are no minutes, no vote split and no dot plot. Every forward-"
                    "guidance study written for a G10 bank is inapplicable here, and the pack "
                    "says so rather than substituting a proxy.",
    "timezone": "AST = UTC+3 all year. Saudi Arabia observes NO daylight saving, so the Riyadh "
                "clock is fixed while the broker's server moves (UTC+2 winter, UTC+3 summer) -- "
                "every broker-hour mapping in an SA study must be recomputed per season.",
    "fx_operations": (
        "SAMA deals the peg directly with the banks at 3.7500 and does not run a fixing auction. "
        "The defended level is a POLICY, so the observable is never the spot rate: it is the "
        "forward points, SAIBOR against SOFR, and the level of SAMA's net foreign assets. In the "
        "2015-2016 episode 12-month USDSAR forwards reached several hundred points and SAMA "
        "instructed banks to stop offering riyal options -- the price of the peg showed up in "
        "funding and in the forward curve, never in spot."),
    "balance_sheet": "SAMA's net foreign assets (الاحتياطي) are the petrodollar meter: published "
                     "monthly, they fall when the oil bill does not cover the budget and rise "
                     "when it does. The PIF's transfers out of SAMA are a separate flow and a "
                     "drop that is a transfer is not a drop that is a deficit.",
    "liquidity_tools": "SAMA bills, repo/reverse repo, and direct deposits placed with banks when "
                       "SAIBOR runs away from the dollar curve (done in 2022 and again in 2023). "
                       "A deposit injection is an ANNOUNCED event with a date.",
    "falsifier": "SAMA moves its repo rate on a date with no FOMC decision and no peg stress, "
                 "three times in a row, and the 'Saudi policy is US policy' claim in this pack is "
                 "dead.",
}


# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: dict[str, Any] = {
    "peg": {
        "rate": 3.7500,
        "since": "1986-06 (the riyal was pegged to the SDR from 1981 and to the dollar at 3.75 "
                 "from June 1986)",
        "mechanics": "SAMA deals with licensed banks at the peg; spot has traded in a band of a "
                     "few pips (roughly 3.7495-3.7520) for four decades",
        "what_a_break_looks_like": "spot does not move first. Forward points widen, SAIBOR "
                                   "detaches from SOFR, riyal option offers are withdrawn, and "
                                   "commentary in Arabic switches from ربط الريال (the riyal "
                                   "peg) to فك الارتباط (de-pegging). Those four are the "
                                   "observables and they are ordered.",
    },
    "saibor": {
        "name": "SAIBOR (السايبور) -- Saudi Arabian Interbank Offered Rate",
        "tenors": "overnight, 1w, 1m, 3m, 6m, 12m",
        "published_local": "about 11:00 AST",
        "published_utc": "08:00 UTC",
        "administration": "contributed by a panel of Saudi banks under SAMA's benchmark "
                          "framework; SAMA publishes the history in its own statistics",
        "why_it_matters": "3M SAIBOR minus 3M SOFR is the peg-stress spread and the cleanest "
                          "single number in this pack. It widened through 2022-2023 on a loan-to-"
                          "deposit squeeze rather than on peg doubt, which is exactly why the "
                          "spread must be conditioned on deposits before it is read as stress.",
    },
    "osp": {
        "name": "Official Selling Prices (سعر البيع الرسمي)",
        "publisher": "the national oil company, monthly",
        "timing": "normally on or about the fifth of each month, for the following month's "
                  "loadings, announced after the Asian close and before the US open",
        "definition": "a differential to a regional marker (Oman/Dubai average for Asia, ASCI for "
                      "the US, ICE Brent for northwest Europe) per grade -- Arab Light is the one "
                      "the tape reacts to",
        "why_it_matters": "it is an ADMINISTERED price with a timestamp: a discretionary "
                          "announcement about the marginal barrel, made by the producer who sets "
                          "it. That is an event study, not a regression on a commodity index.",
    },
    "pos_week": {
        "name": "the SAMA point-of-sale week (نقاط البيع)",
        "week_ends": "Saturday; the release covers Sunday through Saturday",
        "publication": "the following week, normally Tuesday or Wednesday",
        "fields": "value of transactions, number of transactions, number of terminals, and a "
                  "merchant-category split (food, restaurants, clothing, hotels, jewellery...)",
        "why_it_matters": "the highest-frequency domestic-demand series any major oil exporter "
                          "publishes. Its seasonality is HIJRI -- Ramadan lifts food and clothing "
                          "and crushes restaurants, Eid spikes jewellery and travel -- so a "
                          "Gregorian month dummy cannot absorb it and a study that uses one is "
                          "fitting the moon with a calendar.",
    },
    "dst": "NONE in Saudi Arabia. The two DST transitions that matter to an SA study are the US "
           "one (which moves the FOMC and the OSP reaction window against Riyadh) and the venue's "
           "own.",
}

SETTLEMENT_CONVENTIONS: dict[str, Any] = {
    "spot_fx": "T+2 against the peg; riyal settlement runs through SARIE, SAMA's RTGS",
    "equity_settlement": "T+2 at the Saudi Exchange, cleared by Muqassa since 2020; foreign "
                         "investors settle through qualified custodians (QFI) and the resulting "
                         "FX leg lands one to two sessions after the trade",
    "trading_week": "SUNDAY TO THURSDAY. This is the single most under-used fact about the Gulf "
                    "on this desk: Tadawul opens at 07:00 UTC on SUNDAY, while the FX and CFD "
                    "tape is still shut until about 21:00-22:00 UTC. A weekend shock -- an OPEC+ "
                    "communique, a drone strike, a Sunday OPEC meeting -- is therefore PRICED IN "
                    "RIYADH BEFORE IT IS PRICED ANYWHERE THE DESK TRADES. The Gulf Sunday is a "
                    "free look at Monday's open and the pack treats it as one.",
    "month_end": "government salaries are paid around the 27th of the Gregorian month (moved from "
                 "a Hijri schedule); the POS series shows the pay-cycle spike and any weekly "
                 "study must condition on it",
    "ramadan_hours": "bank and government hours shorten through Ramadan; exchange hours have been "
                     "kept through recent Ramadans but this is DECLARED, not verified on this box "
                     "-- an intraday study spanning Ramadan must check the session table first",
    "settlement_of_oil": "OSP differentials apply to the following month's loadings, so the cash "
                         "flow of an OSP announcement lands 30-60 days after the print; the price "
                         "reaction is immediate and the physical flow is not, and they are two "
                         "different studies",
}

EXCHANGES: dict[str, Any] = {
    "cash": {
        "name": "Saudi Exchange (تداول / Tadawul): TASI, MT30, the Nomu parallel market",
        "week": "Sunday to Thursday; closed Friday and Saturday",
        "hours_local": "10:00-15:00 AST",
        "hours_utc": "07:00-12:00 UTC",
        "pre_open_auction": "09:30-10:00 AST (06:30-07:00 UTC)",
        "closing_auction": "15:00-15:10 AST (12:00-12:10 UTC), a single-price call",
        "price_limit": "+/-10% daily for TASI constituents; +/-30% on Nomu",
        "indices": "TASI (المؤشر العام) is the all-share; MT30 is the thirty-name index the "
                   "futures reference",
    },
    "derivatives": {
        "name": "Saudi Exchange derivatives, cleared by Muqassa",
        "products": "MT30 index futures (listed 2020-08-30) and single-stock futures (2022)",
        "expiry_rule": "DECLARED, NOT VERIFIED ON THIS BOX. The MT30 contract settles on a "
                       "scheduled expiry in the contract month against an index average; the "
                       "exact rule is taken from the exchange's own contract specification and "
                       "this pack refuses to guess it. Any expiry-effect study must read the spec "
                       "first and is UNMEASURED until it does.",
        "liquidity": "thin by global standards; the derivatives market is NOT a usable positioning "
                     "series and is never treated as Korea's KRX file is",
    },
    "foreign_access": {
        "qfi": "Qualified Foreign Investor since 2015, widened in 2016 and 2018",
        "index_inclusion": "MSCI EM and FTSE inclusion ran through 2018-2019 in tranches -- a "
                           "one-off passive inflow of tens of billions of dollars with PUBLISHED "
                           "DATES, which is the cleanest forced-flow event in the pack",
        "reporting": "the exchange publishes trading and ownership by investor nationality "
                     "weekly, which is this market's substitute for a positioning report",
    },
    "gulf_siblings": {
        "qatar": "Qatar Stock Exchange (QSE), Sunday-Thursday, QAR pegged at 3.64",
        "kuwait": "Boursa Kuwait, Sunday-Thursday, KWD pegged to an UNDISCLOSED BASKET -- the one "
                  "GCC currency that is not a dollar peg, and therefore the region's only "
                  "endogenous FX price. Detail lives in the `ae` pack's GULF_SECTIONS.",
    },
}

FISCAL_YEAR_END: dict[str, str] = {
    "government": "31 December. THE FISCAL CALENDAR CHANGED IN 2016: Saudi Arabia ran a HIJRI "
                  "fiscal year until 1437AH and moved to the Gregorian calendar from 2016. Any "
                  "fiscal series pooled across that boundary is pooling years of two different "
                  "lengths, and the 2016 transition year is shorter than both.",
    "budget_cycle": "the budget statement is published in December for the following year, with "
                    "quarterly budget performance reports from the Ministry of Finance about a "
                    "month after each quarter -- those quarterlies carry the realised oil revenue "
                    "and are the fiscal-impulse series this pack uses",
    "corporate": "31 December for listed companies; zakat and tax filings follow the Gregorian "
                 "year since the same 2016 change",
    "oil_revenue_share": "oil is roughly two thirds of government revenue, so the fiscal impulse "
                         "is a LAGGED FUNCTION OF THE OIL PRICE and cannot be treated as an "
                         "independent shock in the same regression as crude",
}


# --------------------------------------------------------------------------- holidays
#: THE HIJRI PROBLEM, STATED ONCE. Eid al-Fitr and Eid al-Adha are Hijri dates fixed by the actual
#: SIGHTING OF THE CRESCENT by the Saudi Supreme Court, announced one or two days ahead. An
#: astronomical calculation is a good estimate and is NOT the announcement: the two differ by a day
#: often enough that a market-closure table built from the calculation alone will be wrong about
#: several sessions a decade. 2024 and 2025 below are the ANNOUNCED dates; 2026 is the
#: astronomical estimate and is labelled as such in `status`.
_SA_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-02-22": "يوم التأسيس Founding Day",
        "2024-04-08": "إجازة عيد الفطر Eid al-Fitr break begins (Ramadan 29)",
        "2024-04-09": "إجازة عيد الفطر Eid al-Fitr break",
        "2024-04-10": "عيد الفطر Eid al-Fitr (1 Shawwal 1445, announced by sighting)",
        "2024-04-11": "إجازة عيد الفطر Eid al-Fitr break",
        "2024-06-15": "يوم عرفة Day of Arafat (9 Dhu al-Hijjah 1445)",
        "2024-06-16": "عيد الأضحى Eid al-Adha (10 Dhu al-Hijjah 1445)",
        "2024-06-17": "إجازة عيد الأضحى Eid al-Adha break",
        "2024-06-18": "إجازة عيد الأضحى Eid al-Adha break",
        "2024-09-23": "اليوم الوطني السعودي Saudi National Day",
    },
    2025: {
        "2025-02-23": "يوم التأسيس Founding Day observed (22 February is a Saturday)",
        "2025-03-30": "عيد الفطر Eid al-Fitr (1 Shawwal 1446, announced by sighting)",
        "2025-03-31": "إجازة عيد الفطر Eid al-Fitr break",
        "2025-04-01": "إجازة عيد الفطر Eid al-Fitr break",
        "2025-06-05": "يوم عرفة Day of Arafat (9 Dhu al-Hijjah 1446)",
        "2025-06-06": "عيد الأضحى Eid al-Adha (10 Dhu al-Hijjah 1446)",
        "2025-06-08": "إجازة عيد الأضحى Eid al-Adha break",
        "2025-06-09": "إجازة عيد الأضحى Eid al-Adha break",
        "2025-09-23": "اليوم الوطني السعودي Saudi National Day",
    },
    2026: {
        "2026-02-22": "يوم التأسيس Founding Day",
        "2026-03-19": "إجازة عيد الفطر Eid al-Fitr break begins (ESTIMATE)",
        "2026-03-20": "عيد الفطر Eid al-Fitr (1 Shawwal 1447, ASTRONOMICAL ESTIMATE -- the "
                      "announced date is decided by crescent sighting and may be 03-19 or 03-21)",
        "2026-03-22": "إجازة عيد الفطر Eid al-Fitr break (ESTIMATE)",
        "2026-05-26": "يوم عرفة Day of Arafat (9 Dhu al-Hijjah 1447, ESTIMATE)",
        "2026-05-27": "عيد الأضحى Eid al-Adha (10 Dhu al-Hijjah 1447, ASTRONOMICAL ESTIMATE)",
        "2026-05-28": "إجازة عيد الأضحى Eid al-Adha break (ESTIMATE)",
        "2026-09-23": "اليوم الوطني السعودي Saudi National Day",
    },
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": (
        "Saudi market closures come from two layers and only one of them is computable. "
        "(1) SOLAR, FIXED AND KNOWN YEARS AHEAD: اليوم الوطني (Saudi National Day) on 23 September "
        "and يوم التأسيس (Founding Day) on 22 February, each moved to an adjacent weekday when it "
        "falls on the Friday-Saturday weekend. "
        "(2) HIJRI, AND FIXED BY SIGHTING RATHER THAN BY ARITHMETIC: عيد الفطر (1 Shawwal, a "
        "multi-session exchange break around it) and عيد الأضحى (10 Dhu al-Hijjah, with يوم عرفة "
        "the day before). The Hijri year is about 354 days, so both walk BACKWARD through the "
        "Gregorian year by roughly eleven days each year -- which is why an Eid effect cannot be "
        "captured by a Gregorian month dummy and why pooling ten years of 'April' is pooling "
        "Ramadan with Eid with neither. "
        "THE RULE THIS PACK USES: the astronomical new moon gives a CANDIDATE date; the Saudi "
        "Supreme Court's sighting announcement, one to two days ahead, gives the ACTUAL date; the "
        "exchange then publishes its own multi-session break, which is longer than the public "
        "holiday. Any study anchored on Eid must use the ANNOUNCED date, must allow +/-1 day, and "
        "must state which it used. A table built from arithmetic alone is wrong about several "
        "sessions a decade and silently so."),
    "authority": "Saudi Supreme Court crescent-sighting announcements, Council of Ministers "
                 "holiday decisions, and the Saudi Exchange's own trading-holiday notice",
    "table": _SA_HOLIDAYS,
    "status": {
        2024: "ANNOUNCED -- Eid al-Fitr 1445 fell on 2024-04-10 and Eid al-Adha 1445 on "
              "2024-06-16 by sighting",
        2025: "ANNOUNCED -- Eid al-Fitr 1446 fell on 2025-03-30 and Eid al-Adha 1446 on "
              "2025-06-06 by sighting",
        2026: "ASTRONOMICAL_ESTIMATE -- 1 Shawwal 1447 is estimated at 2026-03-20 and 10 Dhu "
              "al-Hijjah 1447 at 2026-05-27. NEITHER IS ANNOUNCED YET. The sighting may move "
              "each by a day in either direction and the exchange break around it is longer than "
              "the public holiday. Saudi National Day 2026-09-23 and Founding Day 2026-02-22 are "
              "solar and certain.",
    },
    "market_effect": (
        "Crude, gold and the dollar keep trading through every Saudi closure -- the closure is a "
        "LIQUIDITY regime for the Gulf's own risk, not an absence of price. What actually changes "
        "is the flow: the Eid break stops Saudi bank settlement for several days, POS spending "
        "spikes before it and collapses during it, and the reopening session is the only Gulf "
        "session in the year that prices a week of accumulated news at once. That asymmetry is "
        "the tradable object; the closure itself is not."),
    "callable": "countries.sa.pack:holidays",
}


def holidays(year: int) -> dict[str, str]:
    """The Saudi closure table for one year, `{"YYYY-MM-DD": name}`. `{}` if untabulated."""
    return holiday_table(HOLIDAYS_RULE, year)


def hijri_windows(year: int) -> dict[str, Any]:
    """Ramadan, Eid al-Fitr and Eid al-Adha for one Gregorian year, with the sighting caveat.

    Returned as WINDOWS rather than dates because that is what the observable is: Ramadan is a
    month-long demand regime, Eid is a break with a run-up and a reopening. Every row carries
    `certainty`, and a row whose certainty is ESTIMATE must be studied with a +/-1 day tolerance.
    """
    anchors: dict[int, dict[str, Any]] = {
        2024: {"ramadan_start": "2024-03-11", "eid_al_fitr": "2024-04-10",
               "eid_al_adha": "2024-06-16", "certainty": "ANNOUNCED"},
        2025: {"ramadan_start": "2025-03-01", "eid_al_fitr": "2025-03-30",
               "eid_al_adha": "2025-06-06", "certainty": "ANNOUNCED"},
        2026: {"ramadan_start": "2026-02-18", "eid_al_fitr": "2026-03-20",
               "eid_al_adha": "2026-05-27", "certainty": "ESTIMATE"},
    }
    got = anchors.get(int(year))
    if got is None:
        return {"year": int(year), "certainty": "UNMEASURED",
                "why": "no Hijri anchor tabulated for this year; the crescent sighting is not "
                       "derivable from a weekday rule and this pack will not invent one",
                "windows": ()}
    fitr = date.fromisoformat(str(got["eid_al_fitr"]))
    adha = date.fromisoformat(str(got["eid_al_adha"]))
    ramadan = date.fromisoformat(str(got["ramadan_start"]))
    return {
        "year": int(year), "certainty": got["certainty"],
        "tolerance_days": 1 if got["certainty"] == "ANNOUNCED" else 2,
        "windows": (
            {"name": "رمضان Ramadan", "start": ramadan.isoformat(),
             "end": (fitr - timedelta(days=1)).isoformat(),
             "what": "a demand regime, not a holiday: food and clothing spending up, restaurant "
                     "and daytime activity down, working hours short"},
            {"name": "عيد الفطر Eid al-Fitr", "start": (fitr - timedelta(days=2)).isoformat(),
             "end": (fitr + timedelta(days=3)).isoformat(),
             "what": "the exchange break; POS spikes in the three days before and collapses "
                     "during"},
            {"name": "عيد الأضحى Eid al-Adha", "start": (adha - timedelta(days=1)).isoformat(),
             "end": (adha + timedelta(days=3)).isoformat(),
             "what": "Hajj week; travel, livestock and jewellery spending, and the largest "
                     "single inbound pilgrim flow of the year"},
        ),
        "rule": "sighting-announced where certainty is ANNOUNCED, astronomical estimate "
                "otherwise; any study must state which and allow the tolerance",
    }


def pos_weeks(year: int) -> dict[str, Any]:
    """The SAMA point-of-sale weeks of a Gregorian year: the week END and its expected release.

    Code rather than a table because the rule is computable and a table would rot. The POS week
    runs Sunday to SATURDAY and the release lands the following week; each row is flagged when the
    week overlaps Ramadan or an Eid break, because those weeks are a different regime and pooling
    them with ordinary weeks is what makes the series look seasonal-but-unstable.
    """
    windows = hijri_windows(year).get("windows") or ()
    spans = [(date.fromisoformat(str(w["start"])), date.fromisoformat(str(w["end"])),
              str(w["name"])) for w in windows]
    day = date(year, 1, 1)
    day += timedelta(days=(5 - day.weekday()) % 7)      # Saturday = 5
    rows: list[dict[str, Any]] = []
    while day.year == year:
        start = day - timedelta(days=6)
        overlaps = [name for lo, hi, name in spans if not (hi < start or lo > day)]
        rows.append({"week_end": day.isoformat(), "week_start": start.isoformat(),
                     "expected_release": (day + timedelta(days=3)).isoformat(),
                     "hijri_overlap": tuple(overlaps),
                     "regime": "hijri" if overlaps else "ordinary"})
        day += timedelta(days=7)
    return {"year": int(year), "rule": "POS week ends Saturday; release the following Tuesday or "
                                       "Wednesday", "n_weeks": len(rows), "weeks": tuple(rows),
            "hijri_weeks": tuple(r["week_end"] for r in rows if r["hijri_overlap"]),
            "note": "expected_release is the CONVENTION, not a guarantee; the PIT store keeps the "
                    "actual publication timestamp and the reader uses that one"}


CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("sa_pos_week_calendar",
          domain_ids=("sa_pos_demand_nowcast", "sa_hijri_seasonality"),
          kind="calendar",
          entry="countries.sa.pack:pos_weeks",
          cadence_s=86400.0,
          steerable=False,
          notes="A fixed cost. The weekly POS grid and its Hijri overlap must be recomputed every "
                "pass whatever last week yielded, because a weekly study that mislabels a Ramadan "
                "week produces a confident wrong seasonal rather than nothing."),
    miner("sa_hijri_window_miner",
          domain_ids=("sa_hijri_seasonality", "sa_pos_demand_nowcast"),
          kind="calendar",
          entry="countries.sa.pack:hijri_windows",
          cadence_s=86400.0,
          steerable=False,
          notes="Publishes Ramadan and the two Eids as windows with their certainty. An ESTIMATE "
                "row is never silently promoted to an anchor."),
)


# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"id": "cot_absent_sar",
     "name": "CFTC Commitments of Traders -- DECLARED ABSENT for the riyal",
     "covers": "nothing: there is no SAR futures contract at CME and therefore no COT row, in any "
               "report, ever",
     "frequency": "n/a", "lag": "n/a", "root": "cftc.gov", "licence": "free, public",
     "note": "DECLARED BY NAME so no study reaches for 'speculative riyal positioning'. The same "
             "is true of AED, QAR and KWD. The COT series that DO matter to this pack are the "
             "CRUDE OIL ones (WTI and Brent managed money), because Saudi supply policy acts on "
             "exactly that positioning -- and those are read from the desk's existing cot axis."},
    {"id": "tadawul_nationality_flows",
     "name": "Saudi Exchange trading and ownership by investor nationality",
     "covers": "weekly net purchase and ownership share for foreign institutions (QFI and swap), "
               "GCC investors, and Saudi individuals and institutions",
     "frequency": "weekly", "lag": "a few days after the Thursday close",
     "root": "saudiexchange.sa", "licence": "free, public",
     "note": "This market's substitute for a positioning report, and it is a FLOW: a large "
             "foreign net buy says nothing about the level of foreign ownership, which is "
             "published separately."},
    {"id": "opec_production_surveys",
     "name": "OPEC Monthly Oil Market Report secondary sources, and the JMMC communique",
     "covers": "crude production by member, quota compliance, voluntary adjustments",
     "frequency": "monthly (report) and roughly two-monthly (JMMC)", "lag": "about two weeks",
     "root": "opec.org", "licence": "free, public",
     "note": "The closest thing to a positioning report for the marginal barrel. The SECONDARY "
             "SOURCE estimate and the member's DIRECT COMMUNICATION are two different numbers in "
             "the same table and the gap between them is itself an observable."},
    {"id": "jodi_oil",
     "name": "JODI-Oil World Database -- Saudi Arabia's own submission",
     "covers": "production, refinery intake, exports, and CRUDE BURN for power generation",
     "frequency": "monthly", "lag": "about 60 days", "root": "jodidb.org",
     "licence": "free, public",
     "note": "The only official Saudi export and domestic-burn series. The summer crude burn for "
             "air conditioning is a genuine seasonal that removes barrels from the export market "
             "and is invisible in production data alone."},
    {"id": "tanker_tracking_licensed",
     "name": "Seaborne crude export tracking (Kpler, Vortexa, ClipperData and similar)",
     "covers": "cargo-level Saudi exports by destination, near real time",
     "frequency": "daily", "lag": "days", "root": "(commercial vendors)",
     "licence": "LICENSED -- named here and NEVER fetched, scraped or redistributed",
     "note": "Catalogued so the gap is visible: the desk's export view is JODI at a 60-day lag, "
             "and the real-time view is a paid product it does not hold. That is UNMEASURED by "
             "name, not an absent mechanism."},
)


# --------------------------------------------------------------------------- terminology
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "core": ("الريال السعودي", "ربط الريال", "سعر الصرف", "الدولار", "فك الارتباط",
             "سعر الفائدة", "ساما", "البنك المركزي السعودي", "السايبور", "السيولة"),
    "sa_policy_peg": ("سعر الفائدة", "معدل إعادة الشراء", "إعادة الشراء المعاكس", "ربط الريال",
                      "الاحتياطي", "صافي الأصول الأجنبية", "الاحتياطيات الأجنبية", "ساما",
                      "السياسة النقدية", "خفض الفائدة", "رفع الفائدة", "الفيدرالي الأمريكي"),
    "sa_pos_demand_nowcast": ("نقاط البيع", "المبيعات", "الإنفاق الاستهلاكي", "عمليات الشراء",
                              "أجهزة نقاط البيع", "المدفوعات الإلكترونية", "مدى",
                              "قيمة المبيعات", "عدد العمليات", "الإنفاق الأسبوعي"),
    "sa_money_liquidity": ("المعروض النقدي", "عرض النقود", "الودائع", "الودائع تحت الطلب",
                           "الودائع الزمنية", "السيولة", "القروض", "الائتمان المصرفي",
                           "نسبة القروض إلى الودائع", "فائض السيولة"),
    "sa_oil_policy": ("أوبك", "أوبك+", "حصة الإنتاج", "خفض الإنتاج", "الإنتاج الطوعي",
                      "سعر البيع الرسمي", "خام عربي خفيف", "أرامكو", "الطاقة الإنتاجية",
                      "صادرات النفط", "خام برنت", "الخام الأمريكي"),
    "sa_fiscal": ("الميزانية العامة", "العجز", "الفائض", "الإنفاق الحكومي", "الإيرادات النفطية",
                  "الإيرادات غير النفطية", "وزارة المالية", "الدين العام", "صكوك",
                  "نقطة التعادل المالية"),
    "sa_sovereign_flow": ("صندوق الاستثمارات العامة", "الصندوق السيادي", "الاستثمارات الخارجية",
                          "التحويلات", "تحويلات الأجانب", "رؤية 2030", "المشاريع الكبرى"),
    "sa_equity_market": ("تداول", "السوق السعودي", "المؤشر العام", "سوق الأسهم السعودية",
                         "المستثمرون الأجانب", "صافي الشراء", "الاكتتاب", "نمو",
                         "التداولات اليومية", "القيمة السوقية"),
    "sa_banking": ("البنوك السعودية", "السايبور", "ودائع حكومية", "ضخ السيولة",
                   "الاحتياطي النظامي", "كفاية رأس المال", "التمويل العقاري", "أسعار الفائدة"),
    "sa_hijri_seasonality": ("رمضان", "عيد الفطر", "عيد الأضحى", "موسم الحج", "العمرة",
                             "إجازة العيد", "اليوم الوطني", "يوم التأسيس", "الأسبوع الأول",
                             "رؤية الهلال"),
    "sa_energy_risk": ("مضيق هرمز", "الملاحة", "البحر الأحمر", "باب المندب", "ناقلات النفط",
                       "هجوم", "طائرات مسيرة", "منشآت نفطية", "بقيق", "إمدادات النفط"),
    "sa_inflation_macro": ("التضخم", "الرقم القياسي لأسعار المستهلك", "أسعار المستهلك",
                           "الهيئة العامة للإحصاء", "الناتج المحلي الإجمالي", "النمو غير النفطي",
                           "البطالة", "مؤشر مديري المشتريات"),
    "sa_market_vernacular": ("السوق", "ارتفاع", "انخفاض", "مقاومة", "دعم", "سيولة عالية",
                             "تصريف", "تجميع", "مضاربة", "المستثمر الأجنبي"),
}


# --------------------------------------------------------------------------- source discipline
#: THE TEN LAYERS (principal's per-country depth rule, 2026-09-17). A country is never "covered"
#: by five obvious sources. Every source row carries EXACTLY ONE of these, and a pack must either
#: name a source in a layer or name the layer ABSENT WITH A REASON -- blank is not a disposition.
LAYERS: tuple[str, ...] = ("official", "institutional", "academic", "practitioner",
                           "retail_ecology", "app_ecosystem", "media", "archive",
                           "physical_economy", "source_graph")

#: THREE INDEPENDENT LABELS, and their independence is the point. A source can be PUBLIC and
#: FRINGE and PREDICTIVE all at once; collapsing them into one "quality" score is how a desk
#: throws away the only material that was worth keeping.
ACCESS_LABELS: tuple[str, ...] = ("PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA",
                                  "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL", "USER_SUBMITTED",
                                  "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI",
                                  "STOLEN_UNAUTHORIZED")
CREDIBILITY: tuple[str, ...] = ("AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE",
                                "CONTRADICTED", "UNKNOWN")
PREDICTIVE_STATES: tuple[str, ...] = ("UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE",
                                      "NARRATIVE_FEATURE")

#: Access labels the desk may never read from, whatever else is true of them.
FORBIDDEN_ACCESS: frozenset[str] = frozenset({"PRIVATE", "CONFIDENTIAL_MNPI",
                                              "STOLEN_UNAUTHORIZED"})


def me_source(sid: str, label: str, *, layer: str, roots: Sequence[str],
              languages: Sequence[str], licence: str, access_label: str, credibility: str,
              predictive_state: str, queries: Sequence[str], machine_use_allowed: bool = True,
              evidence_weight: float = 1.0, refused_reason: str = "",
              notes: str = "") -> dict[str, Any]:
    """One layered source row: the framework's five fields plus the depth rule's seven.

    `queries` are NATIVE-LANGUAGE and are the actual strings a crawler types -- Arabic or Hebrew,
    including the vernacular a trader would use, never an English phrase translated at query time.
    A miner that searches for "point of sale data Saudi Arabia" finds an English news article; a
    miner that searches for `نقاط البيع الأسبوعية` finds the release.

    FRINGE AND CONTRADICTED MATERIAL IS KEPT, at low weight, as an evidence object. A claim that
    looks false is evidence about what the market believes, and this desk has been shown before
    that a dropped source is indistinguishable from a source nobody found. `machine_use_allowed`
    is False where the terms forbid machine extraction: the row stays, and the crawler never runs.
    """
    if layer not in LAYERS:
        raise ValueError(f"source {sid}: layer {layer!r} is not one of {list(LAYERS)}")
    if access_label not in ACCESS_LABELS:
        raise ValueError(f"source {sid}: access_label {access_label!r} is not recognised")
    if credibility not in CREDIBILITY:
        raise ValueError(f"source {sid}: credibility {credibility!r} is not recognised")
    if predictive_state not in PREDICTIVE_STATES:
        raise ValueError(f"source {sid}: predictive_state {predictive_state!r} is not recognised")
    row = source_class(sid, label, roots=roots, languages=languages, licence=licence, notes=notes)
    row.update({"layer": layer, "access_label": access_label, "credibility": credibility,
                "predictive_state": predictive_state, "queries": tuple(queries),
                "machine_use_allowed": bool(machine_use_allowed),
                "evidence_weight": float(evidence_weight),
                "refused_reason": refused_reason,
                "kept_as_evidence": credibility in ("FRINGE", "CONTRADICTED", "UNRELIABLE")})
    return row


def absent_layer(layer: str, reason: str) -> dict[str, Any]:
    """A layer this country genuinely has nothing in, NAMED with why. Never a blank."""
    if layer not in LAYERS:
        raise ValueError(f"absent layer {layer!r} is not one of {list(LAYERS)}")
    return {"layer": layer, "status": "ABSENT", "reason": reason}


def check_sources(sources: Sequence[Mapping[str, Any]],
                  absent: Sequence[Mapping[str, Any]] = ()) -> list[str]:
    """Every way this source set fails the depth rule, named. An empty list is the only pass."""
    problems: list[str] = []
    seen: dict[str, int] = {}
    for row in sources:
        sid = str(row.get("id") or "<unnamed>")
        layer = str(row.get("layer") or "")
        if layer not in LAYERS:
            problems.append(f"source {sid}: layer {layer!r} is not one of the ten")
            continue
        seen[layer] = seen.get(layer, 0) + 1
        if str(row.get("access_label")) not in ACCESS_LABELS:
            problems.append(f"source {sid}: access_label is not one of the eleven")
        if str(row.get("access_label")) in FORBIDDEN_ACCESS:
            problems.append(f"source {sid}: access_label {row.get('access_label')} may never be "
                            f"read from")
        if str(row.get("credibility")) not in CREDIBILITY:
            problems.append(f"source {sid}: credibility is not one of the six")
        if str(row.get("predictive_state")) not in PREDICTIVE_STATES:
            problems.append(f"source {sid}: predictive_state is not one of the four")
        if not tuple(row.get("queries") or ()):
            problems.append(f"source {sid}: no native-language queries -- a source with no query "
                            f"is a bookmark, not a lane")
        if not row.get("roots"):
            problems.append(f"source {sid}: no roots a crawler could start from")
    declared = {str(a.get("layer")) for a in absent}
    for layer in LAYERS:
        if seen.get(layer):
            continue
        if layer not in declared:
            problems.append(f"layer {layer}: no source and no declared absence -- the depth rule "
                            f"forbids a blank layer")
    for a in absent:
        if not str(a.get("reason") or "").strip():
            problems.append(f"layer {a.get('layer')}: declared absent with no reason")
        if seen.get(str(a.get("layer"))):
            problems.append(f"layer {a.get('layer')}: declared absent AND sourced")
    return problems


def layer_counts(sources: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Sources per layer, for the report. A zero here must be matched by a declared absence."""
    out = dict.fromkeys(LAYERS, 0)
    for row in sources:
        layer = str(row.get("layer") or "")
        if layer in out:
            out[layer] += 1
    return out


# --------------------------------------------------------------------------- source classes
SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    me_source("sa_official_cb", "Saudi Central Bank (SAMA): statistics and the open-data platform",
              layer="official",
              roots=("sama.gov.sa", "sama.gov.sa/ar-sa/EconomicReports",
                     "the SAMA open-data platform: monetary, FX and benchmark rates, payments "
                     "(weekly point-of-sale), reserves, external sector and energy"),
              languages=("ar", "en"),
              licence="free, public; the open-data platform documents an API whose key is named "
                      "in data/secrets/mena_apis.json and never printed",
              access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
              queries=("نقاط البيع الأسبوعية", "المعروض النقدي", "الاحتياطيات الأجنبية",
                       "صافي الأصول الأجنبية", "سعر الفائدة السايبور", "النشرة الإحصائية الشهرية",
                       "ساما البيانات المفتوحة"),
              notes="The single highest-value root in this pack: the only WEEKLY official series "
                    "in the Gulf live here."),
    me_source("sa_official_stats_fiscal", "GASTAT, the Ministry of Finance and the debt office",
              layer="official",
              roots=("stats.gov.sa", "mof.gov.sa", "ndmc.gov.sa", "my.gov.sa"),
              languages=("ar", "en"), licence="free, public",
              access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
              queries=("الرقم القياسي لأسعار المستهلك", "الهيئة العامة للإحصاء",
                       "تقرير الميزانية الربع سنوي", "الإيرادات النفطية", "العجز المالي",
                       "خطة الاقتراض السنوية"),
              notes="The quarterly budget performance report is the fiscal-impulse series; the "
                    "borrowing plan is the issuance calendar."),
    me_source("sa_institutional_exchange", "The Saudi Exchange, the regulator and the clearing "
                                           "house",
              layer="institutional",
              roots=("saudiexchange.sa", "cma.org.sa", "muqassa.com.sa", "edaa.com.sa"),
              languages=("ar", "en"), licence="free, public; respect the exchange's terms of use",
              access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
              predictive_state="UNTESTED",
              queries=("تداول التقارير الأسبوعية", "ملكية المستثمرين الأجانب",
                       "التداول حسب الجنسية", "أيام الإجازات الرسمية للسوق", "المؤشر العام تاسي"),
              notes="The weekly nationality file is this market's substitute for a positioning "
                    "report. Company disclosures are read for EVENT context only."),
    me_source("sa_institutional_research", "Gulf sell-side and data houses, public tier, plus the "
                                           "IMF",
              layer="institutional",
              roots=("argaam.com", "mubasher.info", "aljaziracapital.com.sa research PDFs",
                     "alrajhi-capital.com research", "imf.org Article IV for Saudi Arabia"),
              languages=("ar", "en"),
              licence="public research pages only; NEVER a paywalled terminal and never a "
                      "redistribution of a licensed feed",
              access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
              predictive_state="NARRATIVE_FEATURE",
              queries=("أرقام تقرير", "توقعات أرباح الشركات", "نقطة التعادل المالية",
                       "تقرير المادة الرابعة", "تقديرات النمو غير النفطي"),
              notes="The IMF Article IV carries the fiscal breakeven oil price -- the number that "
                    "links the budget to OPEC+ behaviour."),
    me_source("sa_academic", "Gulf energy and macro literature",
              layer="academic",
              roots=("kapsarc.org (papers and open data)", "papers.ssrn.com (Gulf FX, peg and "
                     "oil-macro literature)", "scholar.google.com Arabic-language economics",
                     "imf.org working papers", "erf.org.eg (the Economic Research Forum)"),
              languages=("en", "ar"),
              licence="mixed: abstracts and working papers free, journal full text often "
                      "licensed; never scrape a paywall",
              access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
              predictive_state="UNTESTED",
              queries=("الاقتصاد السعودي دراسة", "سياسة سعر الصرف الريال", "أثر أسعار النفط",
                       "الإنفاق الحكومي والنمو", "Saudi peg sustainability"),
              notes="KAPSARC is the rare energy research centre that publishes its DATA as well "
                    "as its conclusions."),
    me_source("sa_practitioner", "Saudi practitioners writing in public",
              layer="practitioner",
              roots=("licensed advisers' public columns in Argaam and Al Eqtisadiah",
                     "public Telegram broadcast channels of CMA-licensed advisers",
                     "LinkedIn public posts by Saudi market professionals",
                     "conference and podcast transcripts from Saudi capital-market events"),
              languages=("ar",),
              licence="public web; VERBATIM CLAIMS only, never personal data, never advice, and "
                      "never from a private or paid group",
              access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
              predictive_state="NARRATIVE_FEATURE", evidence_weight=0.4,
              queries=("تحليل فني للسوق السعودي", "توقعات المؤشر العام", "استراتيجية التداول",
                       "صناديق المؤشرات المتداولة", "السيولة في السوق"),
              notes="Kept at low weight AS EVIDENCE: a practitioner claim names a mechanism with "
                    "a date rule inside it, and the claim's confidence is never scored."),
    me_source("sa_retail_ecology", "The Arabic retail investor ecology",
              layer="retail_ecology",
              roots=("hawamer.com (حوامير البورصة)", "argaam.com comment threads",
                     "public X/Twitter Arabic finance hashtags", "public Telegram broadcast "
                     "channels", "Saudi finance YouTube comment sections"),
              languages=("ar",),
              licence="public web; VERBATIM CLAIMS only, no personal data, no private groups",
              access_label="PUBLIC_SOCIAL", credibility="FRINGE", predictive_state="UNTESTED",
              evidence_weight=0.2,
              queries=("#الاسهم_السعودية", "#تداول", "توصية سهم", "الدعم والمقاومة",
                       "تصريف وتجميع", "السوق اليوم", "المضاربين", "متى ينفجر السوق"),
              notes="FRINGE AND KEPT. Retail vernacular is where a crowding or leverage state is "
                    "visible before any official file shows it, and a claim that turns out false "
                    "is still evidence about what the crowd believed. Low weight, never dropped."),
    me_source("sa_app_ecosystem", "The Saudi financial app surface",
              layer="app_ecosystem",
              roots=("public app-store listings and review corpora for Saudi brokerage and "
                     "payment apps (تداول الراجحي, الأهلي تداول, مدى, stc pay)",
                     "app publishers' own public release notes and status pages"),
              languages=("ar", "en"),
              licence="app-store terms forbid bulk machine extraction of listings and reviews",
              access_label="ACCESS_UNCLEAR", credibility="UNKNOWN", predictive_state="UNTESTED",
              machine_use_allowed=True, evidence_weight=0.3,
              queries=("تطبيق تداول الراجحي", "تحديث تطبيق التداول", "مدى تحديث", "أعطال التطبيق"),
              notes="REGISTERED AND NEVER SCRAPED. The layer is real -- app release notes and "
                    "outage reports date payment-rail changes that show up in the POS series -- "
                    "and the terms forbid machine extraction, so the row exists, "
                    "machine_use_allowed is False, and no crawler is pointed at it."),
    me_source("sa_media", "Saudi and pan-Arab financial press, and the state wire",
              layer="media",
              roots=("spa.gov.sa (واس, the state agency: OPEC and budget statements land here "
                     "first)", "aleqt.com (الاقتصادية)", "alriyadh.com", "cnbcarabia.com",
                     "asharqbusiness.com"),
              languages=("ar",),
              licence="public headlines and article text; several outlets forbid bulk text and "
                      "data mining in their terms -- those are registered and not crawled",
              access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
              predictive_state="NARRATIVE_FEATURE",
              queries=("وكالة الأنباء السعودية بيان أوبك", "الميزانية العامة للدولة",
                       "خفض إنتاج طوعي", "سعر البيع الرسمي أرامكو", "تصريحات وزير الطاقة"),
              notes="SPA is the PRIMARY TIMESTAMP for a Saudi official announcement -- a "
                    "voluntary cut appears there before any English wire carries it."),
    me_source("sa_archive", "The archived record, which is the only PIT source for a changed page",
              layer="archive",
              roots=("web.archive.org captures of sama.gov.sa, mof.gov.sa and saudiexchange.sa",
                     "SAMA annual report and statistical bulletin PDF archives",
                     "OPEC's own MOMR archive", "IMF Article IV history"),
              languages=("ar", "en"), licence="public archive; respect each archive's terms",
              access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
              predictive_state="UNTESTED",
              queries=("التقرير السنوي ساما", "النشرة الإحصائية أرشيف", "الميزانية 2016 بيان"),
              notes="A statistics page that is silently restated destroys a vintage. The archive "
                    "is where the FIRST print of a revised series still exists, which is the "
                    "only way a pre-API history can be made point-in-time at all."),
    me_source("sa_physical_economy", "The physical record: barrels, cargoes, pilgrims and "
                                     "terminals",
              layer="physical_economy",
              roots=("jodidb.org (the kingdom's own production, export and crude-burn "
                     "submission)", "opec.org MOMR production tables",
                     "mawani.gov.sa (the ports authority) throughput",
                     "GASTAT Hajj and Umrah pilgrim statistics",
                     "the electricity regulator's load and generation-fuel reporting"),
              languages=("en", "ar"), licence="free, public",
              access_label="PUBLIC", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
              queries=("إحصاءات الحج والعمرة", "حركة الموانئ السعودية", "إنتاج النفط الخام",
                       "صادرات النفط", "استهلاك الوقود لتوليد الكهرباء"),
              notes="The summer crude burn and the Hajj pilgrim count are physical seasonals that "
                    "no financial series shows: barrels that never reach the export market, and a "
                    "consumption surge with a Hijri date."),
    me_source("sa_physical_licensed", "Real-time seaborne cargo tracking",
              layer="physical_economy",
              roots=("(commercial cargo trackers -- named so the gap is visible, never fetched)",),
              languages=("en",),
              licence="LICENSED; redistribution and machine extraction are forbidden by the "
                      "vendors' terms",
              access_label="LICENSED", credibility="RELIABLE", predictive_state="UNTESTED",
              machine_use_allowed=True,
              refused_reason="the desk holds no subscription and the terms forbid extraction; the "
                             "row exists so the 60-day JODI lag is a MEASURED gap rather than an "
                             "unnoticed one",
              queries=("(none -- this row is never queried)",),
              notes="REGISTERED, NOT CRAWLED. Naming the licensed alternative is what turns 'we "
                    "have no real-time export data' from an absence into a measurement."),
    me_source("sa_source_graph", "Who cites whom: aggregators, mirrors and code that names the "
                                 "endpoints",
              layer="source_graph",
              roots=("zawya.com and gulfbase.com as aggregators (which outlet they cite, and how "
                     "fast)", "github.com repositories that call SAMA, GASTAT or Tadawul "
                     "endpoints", "the citation graph around KAPSARC and IMF Saudi papers",
                     "Arabic Wikipedia and Wikidata entries for Saudi economic institutions"),
              languages=("ar", "en"),
              licence="per-source; code repositories are per-repository licensed and are never "
                      "vendored without one",
              access_label="PUBLIC", credibility="UNKNOWN", predictive_state="UNTESTED",
              evidence_weight=0.5,
              queries=("SAMA API github", "Tadawul data python", "مصدر البيانات",
                       "نقلا عن واس", "حسب ما ذكرت الاقتصادية"),
              notes="The graph is a source in its own right: WHICH outlet carries a statement "
                    "first, and which merely repeats it, is the difference between an event "
                    "timestamp and a duplicate. It also finds the endpoint conventions cheaper "
                    "than rediscovering them."),
    me_source("sa_refused_crypto_and_paywalled", "Grounds this pack refuses on purpose",
              layer="source_graph",
              roots=("(none -- this row records a refusal, and refusals are sources the desk has "
                     "decided about, not sources it forgot)",),
              languages=("ar", "en"), licence="n/a",
              access_label="ACCESS_UNCLEAR", credibility="UNKNOWN", predictive_state="UNTESTED",
              machine_use_allowed=True, evidence_weight=0.0,
              refused_reason="crypto-exchange venues, feeds and order books are refused under the "
                             "MT5 universe mandate (2026-08-18); paywalled vendor terminals are "
                             "refused as redistribution; single-name Saudi equities are refused as "
                             "statistical hypothesis ground (two-lane order 2026-09-06); private "
                             "Telegram and WhatsApp groups are refused because they are not public "
                             "sources whatever they contain",
              queries=("(none -- this row is never queried)",),
              notes="Recorded rather than omitted, so a later session can tell a refusal from an "
                    "oversight."),
)

#: Layers this country genuinely has nothing in. NAMED WITH A REASON -- a blank layer is
#: forbidden, and an empty one that is merely unexamined is worse than an admitted gap.
ABSENT_LAYERS: tuple[dict[str, Any], ...] = ()


# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    dataset("sama_pos_weekly",
            source="SAMA weekly point-of-sale transactions (نقاط البيع)",
            coverage="value and number of POS transactions and terminals, with a merchant-"
                     "category split, for a Sunday-to-Saturday week",
            frequency="weekly",
            publication_lag_days=3.0,
            revisions="the weekly figure is not normally revised; it is SUPERSEDED by the monthly "
                      "payments aggregate, which is a different series -- storing only the latest "
                      "value destroys the vintage a point-in-time study needs",
            licence="free, public (SAMA open data terms, attribution required)",
            history_from="2018-01",
            pit_feasible=True,
            assets=("XBRUSD", "XTIUSD", "XAUUSD", "USDX", "US500"),
            mechanism_families=("domestic_demand_nowcast", "consumption_state", "hijri_seasonal",
                                "oil_revenue_pass_through"),
            how_to_fetch="SAMA open-data platform weekly release; store the publication timestamp "
                         "with the value and keep the Hijri overlap flag from "
                         "countries.sa.pack:pos_weeks"),
    dataset("sama_money_supply",
            source="SAMA monetary statistics: M0, M1, M2, M3 and their components",
            coverage="currency outside banks, demand deposits, time and savings deposits, other "
                     "quasi-money; the weekly aggregate where SAMA publishes one",
            frequency="monthly, with a weekly aggregate in SAMA's weekly release (DECLARED, "
                      "verified only when the lane returns bytes)",
            publication_lag_days=25.0,
            revisions="minor restatements into the annual bulletin; both vintages are kept",
            licence="free, public",
            history_from="1993-01",
            pit_feasible=True,
            assets=("XAUUSD", "USDX", "XBRUSD", "US500"),
            mechanism_families=("liquidity_state", "petrodollar_recycling", "credit_cycle"),
            how_to_fetch="SAMA open-data monetary statistics; the weekly series is the "
                         "high-frequency liquidity state and the monthly one is its anchor"),
    dataset("sama_net_foreign_assets",
            source="SAMA net foreign assets and official reserve assets (الاحتياطي)",
            coverage="total reserve assets, foreign securities, deposits abroad, gold and the IMF "
                     "position",
            frequency="monthly",
            publication_lag_days=30.0,
            revisions="occasional reclassification between deposits and securities; the level is "
                      "not normally restated",
            licence="free, public",
            history_from="1993-01",
            pit_feasible=True,
            assets=("XAUUSD", "USDX", "UST10Y", "US500"),
            mechanism_families=("petrodollar_recycling", "peg_defence", "sovereign_flow"),
            how_to_fetch="SAMA open-data external-sector statistics; a fall that is a PIF transfer "
                         "is not a fall that is a deficit and the two must be separated before "
                         "the series is used"),
    dataset("sama_bank_deposits_credit",
            source="SAMA banking statistics: deposits, bank credit, loan-to-deposit ratio",
            coverage="government and private deposits, credit by sector and maturity",
            frequency="monthly",
            publication_lag_days=30.0,
            revisions="minor",
            licence="free, public",
            history_from="1993-01",
            pit_feasible=True,
            assets=("XAUUSD", "USDX", "US500"),
            mechanism_families=("liquidity_state", "credit_cycle", "funding_stress"),
            how_to_fetch="SAMA open-data banking statistics; the loan-to-deposit ratio is the "
                         "variable that explains the 2022-2023 SAIBOR widening without any peg "
                         "doubt at all, and it is the control that widening must be read against"),
    dataset("saibor_daily",
            source="SAMA benchmark statistics: SAIBOR by tenor",
            coverage="overnight to 12-month interbank offered rates",
            frequency="daily",
            publication_lag_days=0.4,
            revisions="none once fixed",
            licence="free, public",
            history_from="2000-01",
            pit_feasible=True,
            assets=("XAUUSD", "USDX", "UST10Y"),
            mechanism_families=("funding_stress", "peg_defence", "policy_state"),
            how_to_fetch="SAMA statistics; published about 11:00 AST (08:00 UTC). The tradable "
                         "quantity is SAIBOR minus the dollar curve, never the level"),
    dataset("sama_payments_monthly",
            source="SAMA payment-system statistics (SARIE, mada, cheques, e-commerce)",
            coverage="volume and value of clearing, card and e-commerce payments",
            frequency="monthly",
            publication_lag_days=30.0,
            revisions="minor",
            licence="free, public",
            history_from="2015-01",
            pit_feasible=True,
            assets=("XBRUSD", "US500", "USDX"),
            mechanism_families=("domestic_demand_nowcast", "consumption_state"),
            how_to_fetch="SAMA open-data payments statistics; the monthly aggregate is the anchor "
                         "the weekly POS series is benchmarked against"),
    dataset("gastat_cpi",
            source="GASTAT consumer price index (الهيئة العامة للإحصاء)",
            coverage="headline and core CPI, with the housing and rent component that dominates it",
            frequency="monthly",
            publication_lag_days=15.0,
            revisions="rare",
            licence="free, public",
            history_from="2014-01",
            pit_feasible=True,
            assets=("XAUUSD", "USDX"),
            mechanism_families=("inflation_state", "real_rate"),
            how_to_fetch="stats.gov.sa monthly release. Under the peg the real policy rate is a "
                         "US nominal rate minus a Saudi price index, which is the whole reason "
                         "this series belongs in an FX-free pack"),
    dataset("mof_budget_quarterly",
            source="Ministry of Finance quarterly budget performance report",
            coverage="realised oil and non-oil revenue, expenditure, the deficit and financing",
            frequency="quarterly",
            publication_lag_days=35.0,
            revisions="each quarter restates the year to date; VINTAGES MATTER and are kept",
            licence="free, public",
            history_from="2017-Q1",
            pit_feasible=True,
            assets=("XBRUSD", "XTIUSD", "USDX", "UST10Y"),
            mechanism_families=("fiscal_impulse", "oil_revenue_pass_through", "sovereign_flow"),
            how_to_fetch="mof.gov.sa quarterly report PDF and data annex about five weeks after "
                         "quarter end"),
    dataset("jodi_oil_saudi",
            source="JODI-Oil World Database, Saudi Arabia submission",
            coverage="crude production, exports, refinery intake, direct crude burn and stocks",
            frequency="monthly",
            publication_lag_days=60.0,
            revisions="frequently revised for up to a year; EVERY VINTAGE IS KEPT because the "
                      "first print is what the market traded",
            licence="free, public",
            history_from="2002-01",
            pit_feasible=True,
            assets=("XBRUSD", "XTIUSD", "XNGUSD"),
            mechanism_families=("supply_state", "seasonal_burn", "export_cycle"),
            how_to_fetch="jodidb.org bulk download; the 60-day lag means this is a REGIME "
                         "variable, never a trigger"),
    dataset("opec_production_mombr",
            source="OPEC Monthly Oil Market Report production table",
            coverage="crude production by member from secondary sources AND from direct "
                     "communication -- two numbers, and the gap between them is an observable",
            frequency="monthly",
            publication_lag_days=14.0,
            revisions="the prior month is routinely revised",
            licence="free, public",
            history_from="2003-01",
            pit_feasible=True,
            assets=("XBRUSD", "XTIUSD"),
            mechanism_families=("supply_state", "quota_compliance", "policy_signal"),
            how_to_fetch="opec.org MOMR PDF and its data appendix, mid-month"),
    dataset("aramco_osp_monthly",
            source="Official Selling Price announcements for Arab Light and the other grades",
            coverage="the differential to the regional marker per grade and per destination "
                     "region (Asia, NW Europe, US, Mediterranean)",
            frequency="monthly",
            publication_lag_days=0.1,
            revisions="none: an OSP is announced once and applies to the next month's loadings",
            licence="public announcement; the press carries it, several vendors resell it",
            history_from="2005-01",
            pit_feasible=True,
            assets=("XBRUSD", "XTIUSD"),
            mechanism_families=("administered_price", "policy_signal", "demand_read"),
            how_to_fetch="the producer's own announcement, normally on or about the fifth, "
                         "carried by SPA first; store the announcement timestamp, not the date "
                         "of the month it applies to"),
    dataset("tadawul_nationality_weekly",
            source="Saudi Exchange weekly trading and ownership by investor nationality",
            coverage="net purchase and ownership share by investor class and nationality",
            frequency="weekly",
            publication_lag_days=4.0,
            revisions="none once published",
            licence="free, public",
            history_from="2015-06",
            pit_feasible=True,
            assets=("US500", "NAS100", "XAUUSD"),
            mechanism_families=("foreign_flow", "risk_appetite", "gulf_risk_state"),
            how_to_fetch="saudiexchange.sa market reports; used as a GULF RISK STATE input, never "
                         "as a signal on a Saudi name"),
    dataset("sa_forward_points_commentary",
            source="public commentary and central-bank discussion of USDSAR forward points",
            coverage="the 12-month forward, when it is discussed at all",
            frequency="irregular",
            publication_lag_days=1.0,
            revisions="n/a",
            licence="public commentary only",
            history_from="2015-08",
            pit_feasible=False,
            assets=("XAUUSD", "USDX"),
            mechanism_families=("peg_defence", "funding_stress"),
            how_to_fetch="NOT SYSTEMATICALLY AVAILABLE. pit_feasible is False and stays False "
                         "until a public archive with timestamps is found; a peg-stress study "
                         "built on this series can only ever produce NOT_PIT_SAFE cells and the "
                         "catalogue says so up front"),
)


# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    actor("SAMA reserve manager",
          holds="the kingdom's official reserve assets: foreign securities, deposits abroad and "
                "gold, against a currency board-like commitment to sell dollars at 3.75",
          forced_to=("meet every dollar bid at the peg, whatever the oil price",
                     "fund the government's draw when oil revenue undershoots the budget",
                     "transfer capital to the sovereign fund when instructed"),
          when="continuously at the peg; the monthly reserve print is the only public measurement",
          information=("the oil price and the realised budget", "the banking system's dollar "
                       "demand", "instructions from the fiscal authority"),
          constraints=("the peg is a stated policy commitment, not a discretionary target",
                       "reserve composition is disclosed only in aggregate"),
          instruments=("USD deposits and securities", "gold", "the domestic repo"),
          counterparties=("Saudi commercial banks", "the US Treasury market", "the sovereign fund"),
          observables=("net foreign assets monthly", "SAIBOR against the dollar curve",
                       "SAMA deposit placements with banks"),
          impact="a persistent bid or offer in US duration and, at the margin, in gold",
          persistence="policy-driven and decades long; it does not learn and does not stop",
          falsifier="reserves and the oil price decouple over three consecutive years with no "
                    "sovereign-fund transfer to explain it",
          notes="This actor is why Saudi Arabia belongs in a US rates and gold study at all."),
    actor("the Public Investment Fund (PIF)",
          holds="a sovereign portfolio of domestic megaprojects and foreign public equities",
          forced_to=("fund committed domestic projects on a schedule regardless of the oil price",
                     "raise dollar debt when transfers and returns do not cover the call"),
          when="capital calls cluster around project milestones and the annual budget",
          information=("the domestic project pipeline", "its own funding cost",
                       "transfers received from SAMA and from the oil company's dividend"),
          constraints=("a published target for assets under management",
                       "domestic spending commitments that cannot be deferred quietly"),
          instruments=("USD bonds and sukuk", "foreign listed equities", "domestic projects"),
          counterparties=("international bond investors", "SAMA", "global equity markets"),
          observables=("13F filings for its US holdings", "dollar bond issuance announcements",
                       "SAMA's net foreign assets"),
          impact="a recurring dollar-debt supply and a rules-light global equity bid",
          persistence="strategic and multi-decade, though the SIZE of the call is procyclical "
                      "with oil",
          falsifier="two consecutive years in which PIF issuance and SAMA reserves move in the "
                    "same direction against the oil price",
          notes="Named as a FLOW actor. Its holdings are single names and none of them is ever a "
                "hypothesis here."),
    actor("the national oil company's treasury",
          holds="the world's largest single crude export book and a dividend obligation to the "
                "state",
          forced_to=("pay a committed quarterly dividend whatever the realised price",
                     "fund capex to hold spare capacity",
                     "borrow when the dividend exceeds free cash flow"),
          when="quarterly dividend declarations; monthly OSP announcements around the fifth",
          information=("refinery margins and Asian buying interest",
                       "the freight and Brent-Dubai spread", "state revenue requirements"),
          constraints=("the state's revenue need", "OPEC+ quota", "long-term customer relations"),
          instruments=("physical crude cargoes", "the administered OSP differential",
                       "USD bonds"),
          counterparties=("Asian refiners", "the state", "international bond investors"),
          observables=("the monthly OSP table", "the quarterly dividend",
                       "JODI exports and refinery intake"),
          impact="the OSP is a directional statement about Asian demand that moves the Brent-"
                 "Dubai structure and, through it, the flat price",
          persistence="structural; the OSP mechanism has run monthly for decades",
          falsifier="OSP changes stop leading the Brent-Dubai spread over 36 consecutive months",
          notes="A SENSOR, not a name. Nothing in this pack puts the company on a docket."),
    actor("the National Debt Management Centre",
          holds="the sovereign's local and international debt programme",
          forced_to=("fund the fiscal deficit on an announced annual borrowing plan",
                     "issue into windows the market will take"),
          when="a published issuance calendar, monthly local sukuk and opportunistic dollar deals",
          information=("the realised deficit", "global credit conditions",
                       "the domestic banking system's appetite"),
          constraints=("an annual borrowing plan published with the budget",
                       "a debt-to-GDP ceiling stated as policy"),
          instruments=("riyal sukuk", "USD bonds"),
          counterparties=("Saudi banks", "international credit investors"),
          observables=("the annual borrowing plan", "monthly local issuance results",
                       "the sovereign credit spread"),
          impact="local issuance drains riyal liquidity and shows up in SAIBOR and in the loan-"
                 "to-deposit ratio",
          persistence="policy-driven and persistent while the deficit persists",
          falsifier="three consecutive quarters in which heavy local issuance leaves SAIBOR and "
                    "deposits unmoved",
          notes="This is the channel that turns a fiscal shortfall into a funding observable."),
    actor("Saudi commercial banks",
          holds="a riyal deposit base against a loan book dominated by mortgages and project "
                "finance",
          forced_to=("fund a loan book that grew faster than deposits",
                     "bid for deposits when the ratio tightens",
                     "quote SAIBOR daily as a panel"),
          when="continuous; the strain is visible monthly in the loan-to-deposit ratio",
          information=("their own deposit flows", "SAMA's placements", "the mortgage pipeline"),
          constraints=("a regulatory loan-to-deposit limit", "capital adequacy",
                       "the peg, which removes independent rate setting"),
          instruments=("interbank riyal funding", "SAMA repo", "deposits"),
          counterparties=("SAMA", "each other", "the government as a depositor"),
          observables=("SAIBOR by tenor", "the loan-to-deposit ratio",
                       "government deposits at banks"),
          impact="SAIBOR detaches from the dollar curve on funding strain, which LOOKS like peg "
                 "stress and is not",
          persistence="cyclical with the mortgage and project cycle",
          falsifier="a SAIBOR-SOFR widening that is not accompanied by a loan-to-deposit move in "
                    "the same quarter, twice running",
          notes="This actor is the CONTROL for every peg-stress claim in the pack."),
    actor("the Saudi household",
          holds="salary income, heavily weighted to public-sector pay, and a card-based spending "
                "habit that is measured weekly",
          forced_to=("spend into Ramadan and Eid on a Hijri schedule",
                     "spend within days of the monthly salary date"),
          when="weekly, with a pay-cycle spike near the 27th and Hijri festival peaks",
          information=("salary timing", "subsidy and allowance announcements",
                       "the Hijri calendar"),
          constraints=("public-sector pay scales", "VAT and fee changes announced by decree"),
          instruments=("card spending measured at the point of sale",),
          counterparties=("domestic merchants", "banks as card issuers"),
          observables=("the weekly POS value and count", "the merchant-category split",
                       "the monthly payments aggregate"),
          impact="the cleanest domestic-demand nowcast in the Gulf and a read on whether oil "
                 "revenue is reaching the real economy",
          persistence="behavioural and stable; the Hijri seasonal has run for as long as the "
                      "series has existed",
          falsifier="POS growth and the non-oil GDP print diverge in sign for four consecutive "
                    "quarters",
          notes="THE reason this pack exists at weekly frequency."),
    actor("the OPEC+ quota committee (JMMC) and the Saudi energy ministry",
          holds="the marginal barrel and the only meaningful spare capacity on earth",
          forced_to=("defend a price consistent with the fiscal breakeven",
                     "hold the group together, which sometimes means absorbing a cut alone",
                     "publish a decision after every scheduled meeting"),
          when="scheduled OPEC and JMMC meetings, plus unscheduled voluntary announcements, often "
               "on a SUNDAY when the desk's tape is shut",
          information=("its own production and export data", "OECD inventory estimates",
                       "member compliance"),
          constraints=("the fiscal breakeven oil price", "member cohesion",
                       "US shale's response function"),
          instruments=("production quota", "voluntary adjustments", "the OSP differential"),
          counterparties=("the other OPEC+ members", "consumers", "the futures market"),
          observables=("the meeting communique with its timestamp", "secondary-source production",
                       "the OSP table"),
          impact="a step change in expected supply, priced first in the crude curve's front "
                 "spreads and then in the flat price",
          persistence="institutional and long-lived, though cohesion is the variable",
          falsifier="three consecutive communiques that move neither the front spread nor the "
                    "flat price beyond a matched non-event control",
          notes="The SUNDAY timing is the part of this actor the desk can actually exploit."),
    actor("the foreign passive index fund",
          holds="an emerging-market mandate that had to buy Saudi Arabia on published dates",
          forced_to=("buy the index weight on the inclusion date, at whatever price",
                     "rebalance on each review"),
          when="the 2018-2019 inclusion tranches and every subsequent index review",
          information=("the index provider's published schedule",),
          constraints=("tracking error against a published benchmark",),
          instruments=("Saudi listed equities via QFI and swaps",),
          counterparties=("local sellers", "the exchange"),
          observables=("the index provider's schedule", "the exchange's weekly nationality flows"),
          impact="a dated, size-known, price-insensitive flow -- the cleanest forced flow in the "
                 "whole region",
          persistence="one-off for inclusion, recurring but small for reviews",
          falsifier="an inclusion tranche passes with no measurable foreign net purchase in the "
                    "exchange's own weekly file",
          notes="Studied through the GULF RISK STATE and never as a single name."),
    actor("the expatriate remitter",
          holds="riyal wages earned by a large foreign workforce",
          forced_to=("send a stable share of wages home every month",
                     "send more before Eid and before the school year"),
          when="monthly, with Hijri and school-calendar peaks",
          information=("wage payment dates", "home-currency exchange rates"),
          constraints=("a fee structure, and a remittance-tax debate that has moved the flow "
                       "before",),
          instruments=("retail remittance channels", "the riyal-dollar conversion beneath them"),
          counterparties=("remittance operators", "banks", "recipient economies"),
          observables=("SAMA's monthly remittance outflow series",),
          impact="a persistent, seasonal dollar demand that is one of the largest in the world in "
                 "absolute terms",
          persistence="structural while the workforce composition holds",
          falsifier="the remittance series loses its Hijri seasonal for two consecutive years",
          notes="Under a peg this is dollar demand SAMA must meet, which links it to reserves."),
    actor("the Hajj and Umrah pilgrim flow",
          holds="an inbound seasonal population measured in millions with a Hijri schedule",
          forced_to=("travel in a fixed Hijri window", "spend on travel, lodging and food there"),
          when="the Hajj week around 10 Dhu al-Hijjah and the Ramadan Umrah season",
          information=("the visa quota published each year", "the Hijri calendar"),
          constraints=("a quota set by agreement with sending countries", "physical capacity"),
          instruments=("inbound services spending, visible in the POS category split",),
          counterparties=("domestic merchants, hotels and airlines",),
          observables=("POS hotel and restaurant categories", "the published quota",
                       "air traffic"),
          impact="a services-inflation and consumption seasonal that a Gregorian dummy cannot see",
          persistence="structural and growing with capacity",
          falsifier="the POS travel and hotel categories show no Hajj-week excess against a "
                    "matched non-Hajj week for three consecutive years",
          notes="The clearest demonstration that this economy's seasonality is Hijri."),
    actor("the GCC peg-arbitrage desk",
          holds="riyal, dirham, riyal-qatari and dinar forward books held against the dollar",
          forced_to=("quote a forward curve against a pegged spot",
                     "cover when a client demands protection against a de-peg"),
          when="around oil shocks, geopolitical events and rating actions",
          information=("SAIBOR and EIBOR against the dollar curve", "reserve prints",
                       "credit default swap levels"),
          constraints=("central banks have restricted riyal option offerings before",
                       "position limits on a market with little liquidity"),
          instruments=("USDSAR and USDAED forwards", "sovereign credit protection"),
          counterparties=("corporates hedging receipts", "macro funds expressing a de-peg view"),
          observables=("12-month forward points", "sovereign credit spreads",
                       "central-bank statements about the peg"),
          impact="forward points, not spot, are where a peg is repriced -- and the desk cannot "
                 "trade either, so the signal is expressed in gold, the dollar and crude",
          persistence="episodic; it appears in 2015-2016 style stress and vanishes between",
          falsifier="a period of sustained low oil in which forward points do not widen at all",
          notes="pit_feasible is False for the forward series and the pack says so."),
    actor("the Saudi retail equity investor",
          holds="a leveraged, concentrated position in the local market, historically dominant "
                "in turnover",
          forced_to=("meet margin calls", "reduce risk into a long Eid break"),
          when="daily, with a documented pre-holiday reduction",
          information=("local media and Arabic boards", "official announcements via SPA"),
          constraints=("margin rules", "the Sunday-to-Thursday week"),
          instruments=("Saudi listed equities",),
          counterparties=("local institutions", "foreign QFI investors"),
          observables=("exchange turnover by investor class", "margin statistics where published"),
          impact="the local risk appetite that makes the Gulf Sunday session informative about "
                 "Monday's global open",
          persistence="behavioural and persistent, though the foreign share has risen since 2019",
          falsifier="the Gulf Sunday session stops carrying any information about the Monday open "
                    "of the desk's own instruments over a three-year sample",
          notes="Studied as a GULF RISK STATE, never as a name."),
    actor("the domestic power and desalination system",
          holds="a summer electricity load met partly by burning crude directly",
          forced_to=("burn crude and fuel oil for power in the summer peak",
                     "take barrels away from the export market to do it"),
          when="June to September every year",
          information=("temperature", "the gas-substitution programme's progress"),
          constraints=("installed gas capacity", "a stated policy of displacing crude burn"),
          instruments=("direct crude burn, reported to JODI",),
          counterparties=("the export market, which loses those barrels",),
          observables=("JODI direct crude burn", "the export-minus-production gap"),
          impact="a seasonal reduction in exportable barrels that production data alone cannot see",
          persistence="structural but DECLINING as gas substitution proceeds -- a trend, and any "
                      "study must allow for it",
          falsifier="summer crude burn stops showing a seasonal excess over the winter months for "
                    "three consecutive years",
          notes="The single best argument for reading exports rather than production."),
)


# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    domain("sa_pos_demand_nowcast", "The weekly point-of-sale print as a demand nowcast",
           objects=("POS value and count by week", "the merchant-category split",
                    "the pay-cycle spike", "the monthly payments aggregate as the anchor"),
           conditions=("Hijri overlap (Ramadan, Eid, Hajj)", "the salary week",
                       "the oil-revenue regime of the preceding two quarters"),
           instruments=("XBRUSD", "XTIUSD", "XAUUSD", "USDX", "US500"),
           controls=("matched non-Hijri weeks of the same calendar month",
                     "the same week of the preceding three years",
                     "a placebo target: a G10 cross with no Gulf exposure",
                     "the monthly payments aggregate, which must move with the weekly sum or the "
                     "weekly series is measuring something else"),
           notes="The nowcast is about DOMESTIC demand in the economy that sets oil supply "
                 "policy; the claim is that it conditions the supply reaction, not that it "
                 "forecasts crude on its own."),
    domain("sa_money_liquidity_state", "Money supply and deposits as a Gulf liquidity state",
           objects=("M1, M2, M3 and their growth", "government versus private deposits",
                    "the weekly aggregate where SAMA publishes one"),
           conditions=("the oil price regime", "the fiscal quarter", "local sukuk issuance"),
           instruments=("XAUUSD", "USDX", "US500", "XBRUSD"),
           controls=("the same statistics for the UAE, which shares the peg and not the oil mix",
                     "a US liquidity series, so a global move is not read as a Gulf one",
                     "randomised release dates as a placebo"),
           notes="A state variable, not a trigger: monthly data with a 25-day lag conditions a "
                 "regime and never times an entry."),
    domain("sa_reserves_petrodollar", "Net foreign assets as the petrodollar recycling meter",
           objects=("SAMA net foreign assets", "the split between securities and deposits",
                    "transfers to the sovereign fund"),
           conditions=("the realised oil price", "the fiscal deficit",
                       "announced sovereign-fund transfers"),
           instruments=("XAUUSD", "UST10Y", "USDX", "US500"),
           controls=("the oil price itself, which must be partialled out before any claim",
                     "other exporters' reserves as a common-factor control",
                     "a matched window with no transfer announcement"),
           notes="The mechanism is a FLOW into US duration and gold. Reserves falling because of "
                 "a transfer and reserves falling because of a deficit are different events."),
    domain("sa_peg_stress_funding", "SAIBOR, forwards and what actually repricing a peg looks like",
           objects=("SAIBOR by tenor", "SAIBOR minus the dollar curve",
                    "12-month forward points where observable", "SAMA deposit placements"),
           conditions=("the loan-to-deposit ratio", "the oil price regime",
                       "sovereign credit spreads"),
           instruments=("XAUUSD", "USDX", "XBRUSD"),
           controls=("the loan-to-deposit ratio as the FIRST control -- a widening explained by "
                     "it is not peg stress",
                     "EIBOR against the same dollar curve, since the UAE shares the peg",
                     "a matched calm-period window"),
           notes="pit_feasible is False for the forward series; a cell built on it is "
                 "NOT_PIT_SAFE and is labelled so rather than quietly scored."),
    domain("sa_opec_supply_policy", "OPEC+ decisions as dated supply events",
           objects=("meeting and JMMC communiques with timestamps", "voluntary cut announcements",
                    "secondary-source versus direct-communication production"),
           conditions=("whether the announcement lands on a Sunday when the tape is shut",
                       "the inventory regime", "prior compliance"),
           instruments=("XBRUSD", "XTIUSD", "XNGUSD", "USDCAD", "USDNOK"),
           controls=("matched non-event days at the same hour and weekday",
                     "the pre-announcement drift window, to separate leak from reaction",
                     "a placebo on a non-energy instrument"),
           notes="The Sunday announcements are the ones with a tradable structure, because the "
                 "reaction has to appear at the FX open rather than during the meeting."),
    domain("sa_osp_administered_price", "The monthly official selling price as a demand signal",
           objects=("the Arab Light differential to the Asian marker",
                    "the announcement timestamp", "the change versus the prior month"),
           conditions=("the Brent-Dubai spread at announcement", "refinery margins",
                       "the month of the year"),
           instruments=("XBRUSD", "XTIUSD"),
           controls=("the Brent-Dubai spread itself, partialled out",
                     "matched non-announcement days in the same week",
                     "the same test on a month when the OSP was unchanged"),
           notes="An administered price is a STATEMENT about demand by the party with the best "
                 "information. That is what makes it a signal rather than a quote."),
    domain("sa_fiscal_impulse", "The budget cycle and realised oil revenue",
           objects=("the December budget statement", "quarterly budget performance",
                    "the borrowing plan", "the fiscal breakeven oil price"),
           conditions=("the oil price regime", "the 2016 fiscal-calendar change",
                       "VAT and fee changes"),
           instruments=("XBRUSD", "USDX", "UST10Y", "US500"),
           controls=("the oil price, partialled out first",
                     "the pre-2016 Hijri fiscal years excluded rather than pooled",
                     "a matched non-announcement window"),
           notes="The fiscal breakeven is the variable that links the budget to OPEC+ behaviour, "
                 "and the IMF Article IV is where it is published."),
    domain("sa_gulf_sunday_lead", "The Gulf Sunday session as a free look at Monday",
           objects=("the Sunday Tadawul session return and breadth",
                    "weekend news that lands before the FX open",
                    "the Monday open of the desk's own instruments"),
           conditions=("whether a weekend OPEC+ or geopolitical event occurred",
                       "the size of the Sunday move", "the Hijri calendar"),
           instruments=("XBRUSD", "XTIUSD", "XAUUSD", "US500", "USDJPY"),
           controls=("Sundays with no weekend event, matched by season",
                     "the Friday close-to-Monday open gap in a no-Gulf-session world as the "
                     "baseline",
                     "a placebo instrument with no Gulf exposure"),
           notes="THE structural asymmetry of this civilization: the region trades when the "
                 "desk's venue does not."),
    domain("sa_hijri_seasonality", "Ramadan, Eid and Hajj as demand and liquidity regimes",
           objects=("Ramadan spending patterns", "the Eid break and its reopening",
                    "the Hajj week", "the eleven-day annual drift of the Hijri calendar"),
           conditions=("the Gregorian month the Hijri window lands in",
                       "announced versus estimated Eid dates", "the length of the exchange break"),
           instruments=("XBRUSD", "XAUUSD", "US500"),
           controls=("the same Gregorian weeks in years when the Hijri window fell elsewhere -- "
                     "the drift IS the natural experiment",
                     "matched non-Hijri weeks",
                     "a +/-1 day tolerance on every sighting-announced anchor"),
           notes="Because the Hijri window walks through the Gregorian year, a Gregorian control "
                 "is available for free. Very few seasonals come with one."),
    domain("sa_energy_risk_hormuz", "Physical energy risk in the Gulf and the Red Sea",
           objects=("Strait of Hormuz and Bab al-Mandab transit risk",
                    "attacks on energy infrastructure", "shipping insurance commentary",
                    "the 2019 Abqaiq precedent"),
           conditions=("the level of spare capacity", "the inventory regime",
                       "whether the event lands out of hours"),
           instruments=("XBRUSD", "XTIUSD", "XNGUSD", "XAUUSD", "USDJPY"),
           controls=("matched non-event windows in the same inventory regime",
                     "a placebo on a non-energy instrument",
                     "the decay profile of prior events, so a claim is about persistence and not "
                     "only about the first hour"),
           notes="The persistence question is the whole question: Abqaiq removed half of Saudi "
                 "output and the price effect was largely gone within a fortnight."),
    domain("sa_foreign_flow_risk_state", "Foreign participation as a Gulf risk-appetite state",
           objects=("weekly nationality flows", "index inclusion and review dates",
                    "the foreign ownership share"),
           conditions=("the global risk regime", "the oil regime", "index review windows"),
           instruments=("US500", "NAS100", "XAUUSD"),
           controls=("global EM flows as the common factor",
                     "non-review weeks matched by season",
                     "a placebo on a developed market with no Gulf weight"),
           notes="Used as a state variable for global risk, never as a signal on a Saudi name."),
    domain("sa_inflation_real_rate", "A US nominal rate against a Saudi price level",
           objects=("GASTAT CPI and its rent component", "the imported-goods share",
                    "the VAT changes of 2018 and 2020"),
           conditions=("the peg, which imports US policy",
                       "the two VAT steps, which are level shifts and not inflation",
                       "the rent cycle"),
           instruments=("XAUUSD", "USDX"),
           controls=("the VAT step dates excluded or dummied explicitly",
                     "US CPI as the imported component",
                     "the UAE's CPI as a peg-sharing control"),
           notes="The real policy rate here is a foreign nominal rate minus a domestic price "
                 "index, which is the mechanism a peg actually creates."),
)


# --------------------------------------------------------------------------- transmission seeds
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("sa_pos_to_crude",
         source="SAMA weekly POS value growth, deseasonalised on the HIJRI calendar",
         mechanism="domestic demand in the swing producer conditions how hard its supply policy "
                   "has to defend a price: weak domestic demand with a wide fiscal gap raises the "
                   "probability of a defended cut",
         targets=("XBRUSD", "XTIUSD"),
         sign="weak POS growth -> higher probability of a supply-supportive announcement -> "
              "positive crude drift conditional on the fiscal gap",
         horizon="2 to 8 weeks",
         lag="3 days from week end to publication",
         control="matched non-Hijri weeks and the oil price's own momentum partialled out",
         evidence="HYPOTHESIS",
         notes="Conditional, not direct. The unconditional POS-to-crude correlation is expected "
               "to be near zero and that is not a refutation of this edge."),
    edge("sa_reserves_to_gold",
         source="SAMA net foreign assets, monthly change, with sovereign-fund transfers removed",
         mechanism="petrodollar recycling: a reserve accumulation is a real bid for reserve "
                   "assets, and gold is the part of that bid that is not US duration",
         targets=("XAUUSD", "UST10Y"),
         sign="reserve accumulation -> supportive for gold and for US duration",
         horizon="1 to 3 months",
         lag="30 days",
         control="the oil price partialled out; other exporters' reserves as the common factor",
         evidence="HYPOTHESIS"),
    edge("sa_money_supply_to_risk",
         source="Saudi M3 growth and private deposit growth",
         mechanism="Gulf liquidity is a component of global dollar liquidity when the peg forces "
                   "the recycling: expanding Gulf money is expanding petrodollar deployment",
         targets=("US500", "NAS100", "XAUUSD"),
         sign="accelerating Gulf money growth -> supportive for global risk",
         horizon="1 to 6 months",
         lag="25 days",
         control="US liquidity measures, so a global move is not attributed to the Gulf",
         evidence="HYPOTHESIS"),
    edge("sa_saibor_to_dollar",
         source="3M SAIBOR minus the 3M dollar curve, conditioned on the loan-to-deposit ratio",
         mechanism="a peg-stress spread that survives the funding control is a statement about "
                   "the dollar's scarcity in the region that holds the largest external surplus",
         targets=("USDX", "XAUUSD"),
         sign="a widening that survives the funding control -> dollar-supportive and gold-"
              "supportive together, which is the signature of a stress rather than a growth move",
         horizon="2 weeks to 2 months",
         lag="1 day",
         control="the loan-to-deposit ratio FIRST; EIBOR as the peg-sharing sibling",
         evidence="HYPOTHESIS"),
    edge("sa_osp_to_brent_structure",
         source="the monthly Arab Light OSP differential change to the Asian marker",
         mechanism="an administered price set by the best-informed seller is a statement about "
                   "Asian demand, made before the data that would reveal it",
         targets=("XBRUSD", "XTIUSD"),
         sign="an OSP increase -> the producer sees firm Asian demand -> supportive for the "
              "front of the curve",
         horizon="1 to 20 sessions",
         lag="hours from the announcement",
         control="the Brent-Dubai spread at announcement partialled out; matched non-announcement "
                 "days",
         evidence="HYPOTHESIS"),
    edge("sa_opec_sunday_to_monday_open",
         source="an OPEC+ or JMMC communique published while the desk's venue is closed",
         mechanism="the Gulf trades Sunday and the desk's tape does not, so the information is "
                   "priced in Riyadh first and must arrive at the FX open as a gap",
         targets=("XBRUSD", "XTIUSD", "USDCAD", "USDNOK"),
         sign="the direction of the Sunday Gulf energy reaction -> the sign of the Monday open gap",
         horizon="the first 4 hours of the week",
         lag="up to 14 hours between the Gulf session and the FX open",
         control="Sundays with no communique, matched by season; the ordinary weekend gap "
                 "distribution as the baseline",
         evidence="HYPOTHESIS",
         notes="The most structurally defensible edge in this pack: the asymmetry is a CALENDAR "
               "fact, not a behavioural claim."),
    edge("sa_hormuz_risk_to_oil_gold",
         source="a physical energy-risk event in the Gulf or the Red Sea, timestamped",
         mechanism="a threat to the transit of roughly a fifth of seaborne oil is a supply-"
                   "convexity event; gold carries the geopolitical premium that crude gives back",
         targets=("XBRUSD", "XTIUSD", "XAUUSD", "USDJPY"),
         sign="event -> crude and gold up together, with crude's move decaying faster",
         horizon="1 to 15 sessions",
         lag="minutes to hours",
         control="matched non-event windows in the same inventory and spare-capacity regime; the "
                 "decay profile of prior events",
         evidence="MEASURED_ELSEWHERE",
         notes="MEASURED_ELSEWHERE because the 2019 Abqaiq episode is publicly documented; the "
               "desk has not reproduced it and the seed says so."),
    edge("sa_fiscal_breakeven_to_supply_policy",
         source="the realised deficit and the IMF's fiscal breakeven oil price",
         mechanism="when the market price sits below the breakeven for long enough, the producer's "
                   "incentive to defend price over volume rises -- the budget is the reaction "
                   "function",
         targets=("XBRUSD", "XTIUSD"),
         sign="price below breakeven for two consecutive quarters -> raised probability of a cut "
              "announcement",
         horizon="1 to 2 quarters",
         lag="35 days for the quarterly report",
         control="the oil price's own trend; quarters when price was above breakeven",
         evidence="HYPOTHESIS"),
    edge("sa_hijri_demand_to_softs_and_gold",
         source="the Hijri festival window (Ramadan run-up, Eid, Hajj)",
         mechanism="a dated, population-scale consumption surge with a gold-buying component in a "
                   "region that is a major physical gold market",
         targets=("XAUUSD", "XAGUSD"),
         sign="the pre-Eid window -> physical demand support, decaying through the break",
         horizon="2 to 6 weeks around the window",
         lag="none: the window is known in advance up to the sighting tolerance",
         control="the same Gregorian weeks in years when the Hijri window fell elsewhere",
         evidence="HYPOTHESIS",
         notes="The Hijri drift supplies the control for free, which is rare for a seasonal."),
    edge("sa_summer_burn_to_exports",
         source="JODI direct crude burn and the export-minus-production gap",
         mechanism="barrels burned domestically for summer power are barrels that do not reach "
                   "the export market, so production data overstates supply in summer",
         targets=("XBRUSD", "XTIUSD"),
         sign="a high summer burn -> exports below what production implies -> supportive",
         horizon="1 to 3 months",
         lag="60 days, so this is a REGIME variable and never a trigger",
         control="the declining trend of gas substitution removed first; winter months as the "
                 "within-year control",
         evidence="HYPOTHESIS"),
)


# --------------------------------------------------------------------------- policy eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    era("sa_pre_2014_high_oil", start="2009-01-01", end="2014-06-30",
        label="the hundred-dollar decade",
        what_changed="oil above the fiscal breakeven, reserves accumulating, no VAT, a Hijri "
                     "fiscal year, and a closed equity market",
        invalidates="any study pooling this era with the post-2016 one is pooling a surplus "
                    "economy with a deficit economy and a closed market with an included one"),
    era("sa_2014_16_crash_and_peg_attack", start="2014-07-01", end="2016-12-31",
        label="the oil crash, the peg attack and the fiscal turn",
        what_changed="Brent fell from 115 to 27; 12-month riyal forwards widened to levels "
                     "implying a de-peg; SAMA instructed banks to stop offering riyal options; "
                     "reserves fell by hundreds of billions; the fiscal calendar moved from Hijri "
                     "to Gregorian in 2016; the first Vision 2030 statement landed",
        invalidates="THE reference episode for every peg-stress claim in this pack, and the only "
                    "one in the sample. A peg model estimated without it has never seen stress."),
    era("sa_2017_19_opening", start="2017-01-01", end="2019-12-31",
        label="VAT, index inclusion and the listing of the oil company",
        what_changed="VAT introduced at 5% in January 2018 (a price-level step, not inflation); "
                     "MSCI and FTSE inclusion in 2018-2019 tranches brought tens of billions of "
                     "passive flow with published dates; the oil company listed in December 2019; "
                     "the Abqaiq attack in September 2019 removed half of output for days",
        invalidates="the foreign-ownership share is structurally different before and after "
                    "inclusion, so any flow study must split here"),
    era("sa_2020_covid_and_price_war", start="2020-01-01", end="2020-12-31",
        label="the price war, negative WTI and the VAT tripling",
        what_changed="the March 2020 OPEC+ breakdown and the volume war; WTI settled below zero "
                     "on 2020-04-20, which no model of a positive price survives; VAT tripled "
                     "from 5% to 15% on 2020-07-01; POS spending collapsed and rebounded within "
                     "one quarter",
        invalidates="every crude study must treat April 2020 explicitly; the VAT step is a level "
                    "shift in CPI and is not inflation"),
    era("sa_2021_23_voluntary_cuts", start="2021-01-01", end="2023-12-31",
        label="unilateral voluntary cuts and the 2022 rate cycle",
        what_changed="Saudi Arabia took repeated UNILATERAL voluntary cuts on top of the group "
                     "quota, several announced out of hours; the Fed's hiking cycle was imported "
                     "wholesale through the peg; SAIBOR widened on a loan-to-deposit squeeze "
                     "rather than on peg doubt; SAMA placed deposits with banks to relieve it",
        invalidates="a SAIBOR-based peg-stress indicator estimated on this era is measuring a "
                    "mortgage boom unless the loan-to-deposit ratio is controlled for"),
    era("sa_2024_onward_normalisation", start="2024-01-01", end=None,
        label="the cutting cycle, the unwind of voluntary cuts and a wider non-oil economy",
        what_changed="the Fed's easing imported through the peg from September 2024; the "
                     "voluntary cuts began to be unwound; non-oil activity and the POS series "
                     "carried more of the growth signal than the oil account did",
        invalidates="a supply-policy reaction function fitted on the cut era does not describe an "
                    "unwind era, and the sign of the OPEC+ announcement effect can differ"),
)


# --------------------------------------------------------------------------- the pack
#: THE PACK AS THIS DEPARTMENT WROTE IT, before any framework touches it.
#:
#: `build_pack` hands these twenty-one fields to `libs.research.country_lab.CountryPack` when that
#: module is present, and that dataclass COERCES every row into its own shape -- on 2026-09-17 the
#: coercion mapped an edge's `mechanism` onto `flow` and dropped `id` and `targets` entirely, so
#: `check_pack` reported problems for all twenty-three packs on disk, including the ones written
#: hours earlier. The framework is a sibling builder's live work and it will settle; a pack whose
#: own validity depends on the hour it is read is not a pack.
#:
#: So the department's own row vocabulary is kept HERE, as a mapping, and it is what the tests
#: validate. `pack()` still returns whatever the framework gives, because that is what the
#: scheduler consumes -- the two answers are deliberately separate and both are measured.
FIELDS: dict[str, Any] = {
    "code": CODE,
    "name": NAME,
    "region_command": REGION_COMMAND,
    "currency": CURRENCY,
    "executable_instruments": EXECUTABLE_INSTRUMENTS,
    "central_bank": CENTRAL_BANK,
    "fixing_conventions": FIXING_CONVENTIONS,
    "settlement_conventions": SETTLEMENT_CONVENTIONS,
    "exchanges": EXCHANGES,
    "holidays_rule": HOLIDAYS_RULE,
    "fiscal_year_end": FISCAL_YEAR_END,
    "positioning_sources": POSITIONING_SOURCES,
    "native_languages": NATIVE_LANGUAGES,
    "terminology": TERMINOLOGY,
    "source_classes": SOURCE_CLASSES,
    "datasets": DATASETS,
    "actors": ACTORS,
    "domains": DOMAINS,
    "custom_miners": CUSTOM_MINERS,
    "transmission_edges_seed": TRANSMISSION_EDGES_SEED,
    "policy_eras": POLICY_ERAS,
}


def pack() -> Any:
    """The Saudi Arabia country pack. `CountryPack` when the framework has landed, else a dict."""
    return build_pack(**FIELDS)


def instrument_report(path: Any = None) -> dict[str, Any]:
    """What this pack can trade, what carries its economics, and what is missing -- measured
    against the broker registry rather than asserted."""
    split = resolve(EXECUTABLE_INSTRUMENTS, path)
    return {"code": CODE, "own_price": OWN_PRICE, "executable": tuple(split["tradable"]),
            "equities_refused": tuple(split["equities"]),
            "absent_from_universe": tuple(split["absent"]),
            "transmission_targets": TRANSMISSION_TARGETS,
            "named_absent_instruments": ABSENT_INSTRUMENTS,
            "dataset_fields": DATASET_FIELDS}
