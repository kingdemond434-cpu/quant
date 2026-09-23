"""THE UNITED ARAB EMIRATES COUNTRY PACK -- dollar funding, trade throughput and the Gulf risk tell.

WHY THE UAE IS NOT SAUDI ARABIA WITH A SMALLER OIL FIELD. Saudi Arabia is carried by the marginal
barrel and a weekly demand print. The Emirates are carried by three different things:

  * THE REGION'S DOLLAR FUNDING IS PRICED HERE. The dirham has been pegged at 3.6725 since 1997,
    and since June 2021 the CBUAE's Base Rate sits on its Overnight Deposit Facility, bolted
    directly to the Fed's interest on reserve balances. EIBOR is the Gulf's dollar-funding curve
    wearing a local name, and the EIBOR-minus-SOFR spread -- read against DEPOSIT GROWTH, never
    alone -- is the region's funding stress meter.
  * THE REGION'S GOODS MOVE THROUGH HERE. Jebel Ali is the largest container port between
    Singapore and Rotterdam and Dubai is a re-export economy, so UAE throughput is a WORLD TRADE
    sensor rather than a domestic one. Fujairah, on the Indian Ocean side of the Strait of Hormuz,
    is the world's second bunkering hub, holds a weekly-published oil-product stockpile, and sits
    at the end of the pipeline that exists precisely to bypass Hormuz.
  * THE WEEKEND MOVED, AND ALMOST NOBODY'S CODE KNOWS. On 2022-01-03 the UAE switched to a
    Monday-to-Friday working week. DFM and ADX now trade Monday to Friday; Saudi Arabia, Qatar and
    Kuwait still trade Sunday to Thursday. Before that date the UAE was a Sunday-Thursday market
    too. Any cross-Gulf session study pooled across 2022-01-03 is aligning sessions that were not
    simultaneous, and the Gulf-Sunday-lead mechanism has a DIFFERENT membership before and after.

WHAT THIS PACK MAY NOT DO. USDAED is absent from the broker registry and is named in
`ABSENT_INSTRUMENTS`, never traded. The national oil company, the sovereign funds and the listed
banks are SECTOR OBSERVABLES; their words appear in `TERMINOLOGY` so an Arabic-language miner
recognises them, and none is ever a symbol on a docket (two-lane order, 2026-09-06). No
crypto-exchange ground is hunted (mandate 2026-08-18) -- and that refusal is worth stating twice
in a Gulf pack, because Dubai is a crypto-venue jurisdiction and the temptation is local.

QATAR AND KUWAIT LIVE HERE TOO, as `GULF_SECTIONS`: same funding channel, same risk channel, not
enough independent executable ground for packs of their own.
"""
from __future__ import annotations

from datetime import date
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
)
from countries.sa.pack import (
    LAYERS,
    absent_layer,
    arabic_terms,
    check_sources,
    has_arabic,
    layer_counts,
    me_source,
)

CODE = "ae"
NAME = "United Arab Emirates"
REGION_COMMAND = "MIDDLE_EAST"
CURRENCY = "AED"
NATIVE_LANGUAGES = ("ar", "en")

__all__ = ["LAYERS", "absent_layer", "arabic_terms", "check_sources", "has_arabic",
           "holidays", "instrument_report", "layer_counts", "me_source", "pack",
           "trading_week_on"]

#: The UAE's OWN price on this broker: none. The dirham is a peg, not a quote.
OWN_PRICE: tuple[str, ...] = ()

#: What the AE department may place an order in. Every one is in the broker's registry and none is
#: a single-name equity.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "XBRUSD", "XTIUSD", "XNGUSD", "XAUUSD", "XAGUSD", "USDX", "EURUSD", "USDJPY", "USDINR",
    "USDHKD", "US500", "NAS100", "UST05Y", "UST10Y")

ABSENT_INSTRUMENTS: tuple[dict[str, str], ...] = (
    {"instrument": "USDAED spot",
     "why": "absent from desks/mt5/data/universe/universe.json; the peg at 3.6725 leaves almost "
            "nothing to quote",
     "carried_by": "nothing directly. Peg and funding stress are OBSERVABLES (EIBOR against the "
                   "dollar curve, forward points where public) expressed in XAUUSD, USDX and "
                   "crude"},
    {"instrument": "Murban crude futures (IFAD / ICE Futures Abu Dhabi)",
     "why": "not quoted by this broker",
     "carried_by": "XBRUSD, with the Murban-Brent differential named as an UNMEASURED basis. "
                   "This matters more than a usual basis caveat: since March 2021 Murban is the "
                   "price at which Abu Dhabi actually sells, so a UAE supply study run on Brent "
                   "is one differential away from the object it means to measure"},
    {"instrument": "DFM General Index and the FTSE ADX General Index",
     "why": "no UAE equity index CFD in the broker registry",
     "carried_by": "US500 and NAS100 for the global risk leg and XBRUSD for the energy leg, with "
                   "the Gulf-specific component left UNMEASURED by name"},
    {"instrument": "Qatari riyal, Kuwaiti dinar, Omani rial and Bahraini dinar",
     "why": "none is quoted here",
     "carried_by": "the GULF_SECTIONS observables; the KWD is the only one whose value is not "
                   "mechanically the dollar's, and even it is unreachable as a price"},
    {"instrument": "UAE and Qatari sovereign or bank credit (CDS, USD bonds)",
     "why": "no regional credit instrument is quoted",
     "carried_by": "UST05Y and UST10Y for the duration leg; the regional credit premium is "
                   "UNMEASURED by name and a Gulf-risk claim that needs it must say so"},
)

TRANSMISSION_TARGETS: tuple[str, ...] = ("XBRUSD", "XTIUSD", "XNGUSD", "XAUUSD", "USDX", "USDINR",
                                         "US500", "NAS100", "UST10Y")


# --------------------------------------------------------------------------- central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Central Bank of the United Arab Emirates (CBUAE)",
    "native_name": "مصرف الإمارات العربية المتحدة المركزي",
    "committee": "the Board of Directors; like SAMA, no published vote and no minutes",
    "policy_rate": "the Base Rate on the Overnight Deposit Facility (ODF). Since June 2021 the "
                   "Base Rate is anchored to the US interest on reserve balances (IORB) and moves "
                   "with it; before that the operative rate was the repo rate on Certificates of "
                   "Deposit.",
    "meetings_per_year": 8,
    "schedule_rule": (
        "NO INDEPENDENT CALENDAR, for the same reason as Saudi Arabia: under the 3.6725 peg the "
        "dirham's policy rate is the dollar's. The CBUAE announces a Base Rate change within hours "
        "of the FOMC, so THE UAE DATE LIST IS THE FOMC DATE LIST. The 2021 change of anchor -- "
        "from the CD repo rate to the ODF bolted to IORB -- is a POLICY-FRAMEWORK BREAK, and a "
        "policy series pooled across June 2021 is pooling two different instruments."),
    "minutes_rule": "NONE. No minutes, no vote split, no guidance. Every G10 forward-guidance "
                    "method is inapplicable and the pack says so rather than substituting a proxy.",
    "timezone": "GST = UTC+4 all year, with NO daylight saving -- and note it is one hour ahead of "
                "Riyadh, so a 'Gulf session' is not one clock. Broker-hour mappings must be "
                "recomputed per season because the venue moves and the Gulf does not.",
    "fx_operations": "the CBUAE deals the peg with licensed banks; the observable is never spot. "
                     "It is EIBOR against the dollar curve, the outstanding stock of monetary "
                     "bills (M-Bills, which replaced Certificates of Deposit from 2020), and the "
                     "banking system's liquid-asset ratios.",
    "liquidity_tools": "the Overnight Deposit Facility, monetary bills (M-Bills), and collateral "
                       "facilities. M-Bill issuance is an ANNOUNCED, dated liquidity drain, which "
                       "is what makes the UAE's liquidity state observable at higher frequency "
                       "than its neighbours'.",
    "benchmarks": "EIBOR is published each business day (about 11:00 GST, 07:00 UTC) under CBUAE "
                  "administration, and DONIA, the dirham overnight index average, was introduced "
                  "alongside the ODF framework. DECLARED: the exact DONIA publication time is not "
                  "verified on this box and a study that needs it must check first.",
    "falsifier": "the CBUAE moves its Base Rate on a date with no FOMC decision and no peg or "
                 "funding stress, three times running, and this pack's 'UAE policy is US policy' "
                 "claim is dead.",
}


# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: dict[str, Any] = {
    "peg": {
        "rate": 3.6725,
        "since": "1997-02 formally; the dirham had been held near 3.671 since 1980",
        "mechanics": "the CBUAE deals with banks at the peg; spot moves in fractions of a pip",
        "what_a_break_looks_like": "the same ordered sequence as the riyal: forward points widen "
                                   "first, EIBOR detaches from the dollar curve, option offers "
                                   "are withdrawn, and Arabic commentary shifts from ربط الدرهم "
                                   "to فك الارتباط. Spot is the LAST place a peg is repriced.",
    },
    "eibor": {
        "name": "EIBOR (إيبور) -- Emirates Interbank Offered Rate",
        "tenors": "overnight, 1w, 1m, 3m, 6m, 12m",
        "published_local": "about 11:00 GST",
        "published_utc": "07:00 UTC",
        "administration": "CBUAE as administrator with a contributing bank panel",
        "why_it_matters": "3M EIBOR minus 3M SOFR is the Gulf's dollar-funding stress spread. It "
                          "must be read against DEPOSIT GROWTH and the M-Bill stock: a widening "
                          "that is explained by a liquidity drain is not peg doubt, and the "
                          "2022-2023 Gulf widenings were mostly the former.",
    },
    "donia": {
        "name": "DONIA -- the dirham overnight index average",
        "what": "a transaction-based overnight benchmark introduced with the ODF framework",
        "status": "DECLARED, NOT VERIFIED on this box: publication time and history depth are "
                  "taken from CBUAE documentation and no fetch has confirmed them",
    },
    "murban": {
        "name": "Murban crude, priced on IFAD (ICE Futures Abu Dhabi) since 2021-03-29",
        "what_changed": "Abu Dhabi abandoned retroactive official selling prices for a FORWARD "
                        "FUTURES PRICE. Its supply signal is therefore a market price with a "
                        "continuous timestamp, where Saudi Arabia's is a monthly announcement.",
        "why_it_matters": "a UAE supply study and a Saudi one are different event types and "
                          "cannot share an event window. The Murban-Brent differential is the "
                          "basis and it is UNMEASURED on this box.",
    },
    "fujairah_stocks": {
        "name": "Fujairah oil product stockpiles",
        "publisher": "the Fujairah Oil Industry Zone, distributed publicly each week",
        "cadence": "weekly, normally Wednesday",
        "why_it_matters": "a weekly physical inventory reading at the world's second bunkering "
                          "hub, on the SAFE side of the Strait of Hormuz. It is one of very few "
                          "high-frequency physical energy series in the region that is public.",
    },
    "dst": "NONE. GST is UTC+4 year-round and is one hour ahead of Riyadh.",
}

SETTLEMENT_CONVENTIONS: dict[str, Any] = {
    "spot_fx": "T+2 against the peg, settled through the CBUAE's UAEFTS",
    "equity_settlement": "T+2 at DFM and ADX",
    "trading_week": "MONDAY TO FRIDAY SINCE 2022-01-03. Before that, Sunday to Thursday. THIS IS "
                    "THE MOST CONSEQUENTIAL CALENDAR FACT IN THE PACK: the UAE left the Gulf "
                    "trading week and joined the global one, so a 'Gulf Sunday session' after "
                    "2022 means Saudi Arabia, Qatar and Kuwait -- not the UAE -- and a study that "
                    "pools the UAE into it across that date is averaging two different weeks.",
    "weekend_before_2022": "Friday-Saturday, matching Saudi Arabia; the change also moved the "
                           "Friday half-day and the whole domestic settlement rhythm",
    "month_end": "salary payments through the Wages Protection System cluster at month end; the "
                 "expatriate remittance peak follows within days",
    "ramadan_hours": "shortened working hours are mandated for Ramadan; exchange hours have been "
                     "maintained in recent years but this is DECLARED, not verified here",
    "re_export": "Dubai's trade is dominated by RE-EXPORT, so import and export figures double-"
                 "count transiting goods. A UAE trade balance read like a national one is wrong; "
                 "the throughput is the signal and the balance is not.",
}

EXCHANGES: dict[str, Any] = {
    "cash": {
        "name": "Dubai Financial Market (DFM) and Abu Dhabi Securities Exchange (ADX)",
        "week": "Monday to Friday since 2022-01-03; Sunday to Thursday before it",
        "hours_local": "10:00-15:00 GST (both venues, with an opening auction before)",
        "hours_utc": "06:00-11:00 UTC",
        "indices": "DFM General Index (DFMGI) and the FTSE ADX General Index (FADGI)",
        "foreign_ownership": "raised repeatedly since 2021, including 100% foreign ownership for "
                             "many names -- a structural break in the foreign-flow series",
        "listings": "the 2021-2023 wave of state-linked IPOs (utilities, logistics, energy "
                    "services) changed the index composition materially; an index study pooled "
                    "across it is pooling two indices",
    },
    "derivatives": {
        "name": "DFM and ADX derivatives, plus IFAD for crude",
        "products": "single-stock futures at DFM (from 2020) and ADX; Murban crude futures on "
                    "IFAD (ICE Futures Abu Dhabi) from 2021-03-29",
        "expiry_rule": "DECLARED, NOT VERIFIED on this box for the equity contracts. The Murban "
                       "contract follows the ICE calendar; an expiry study must read the "
                       "specification first and is UNMEASURED until it does.",
        "liquidity": "equity derivatives are thin and are NOT a usable positioning series; Murban "
                     "is genuinely liquid and is the region's only market-priced crude",
    },
    "commodities_and_trade": {
        "gold": "Dubai is one of the world's largest physical gold entrepots (DMCC, the Dubai "
                "Gold and Commodities Exchange, the Dubai Good Delivery standard). Physical "
                "premium and re-export volumes are a genuine gold-demand observable for the "
                "Indian and African corridors.",
        "ports": "Jebel Ali (DP World) container throughput; Khalifa Port; Fujairah bunkering and "
                 "storage",
        "why_here": "these are the UAE's real exchanges as far as this desk is concerned -- the "
                    "flows they measure reach instruments the box can trade, and the equity "
                    "venues do not",
    },
    "gulf_siblings": {
        "qatar": "Qatar Stock Exchange, Sunday to Thursday, QAR pegged at 3.64",
        "kuwait": "Boursa Kuwait, Sunday to Thursday, KWD on an undisclosed basket",
        "detail": "GULF_SECTIONS in this module",
    },
}

FISCAL_YEAR_END: dict[str, str] = {
    "government": "31 December for the federal budget and for each emirate's budget; the federal "
                  "budget is small relative to Abu Dhabi's own spending, so the FEDERAL number is "
                  "not the fiscal impulse and must not be used as one",
    "corporate": "31 December; a federal corporate tax of 9% took effect for financial years "
                 "starting on or after 2023-06-01, which is a level shift in reported earnings "
                 "and not a change in activity",
    "vat": "VAT introduced at 5% on 2018-01-01 -- a price-level step, not inflation",
    "budget_cycle": "Abu Dhabi's spending follows the oil account with a lag; the emirate-level "
                    "numbers are published less completely than Saudi Arabia's, which is why the "
                    "UAE fiscal impulse is UNMEASURED by name in this pack rather than estimated",
}


# --------------------------------------------------------------------------- holidays
#: UAE closures differ from Saudi Arabia's in three ways that matter: the UAE observes the
#: GREGORIAN New Year and the Prophet's Birthday (Saudi Arabia observes neither), it has a
#: two-day national holiday on 2-3 December preceded by Commemoration Day on the 1st, and since
#: 2022 its weekend is Saturday-Sunday rather than Friday-Saturday.
_AE_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-01-01": "رأس السنة الميلادية New Year's Day",
        "2024-04-08": "إجازة عيد الفطر Eid al-Fitr break begins (Ramadan 29)",
        "2024-04-09": "عيد الفطر Eid al-Fitr (announced by sighting)",
        "2024-04-10": "إجازة عيد الفطر Eid al-Fitr break",
        "2024-04-11": "إجازة عيد الفطر Eid al-Fitr break",
        "2024-06-15": "يوم عرفة Day of Arafat",
        "2024-06-16": "عيد الأضحى Eid al-Adha",
        "2024-06-17": "إجازة عيد الأضحى Eid al-Adha break",
        "2024-06-18": "إجازة عيد الأضحى Eid al-Adha break",
        "2024-07-07": "رأس السنة الهجرية Islamic New Year (1446)",
        "2024-09-15": "المولد النبوي Prophet's Birthday",
        "2024-12-01": "يوم الشهيد Commemoration Day",
        "2024-12-02": "اليوم الوطني UAE National Day",
        "2024-12-03": "اليوم الوطني UAE National Day (second day)",
    },
    2025: {
        "2025-01-01": "رأس السنة الميلادية New Year's Day",
        "2025-03-30": "عيد الفطر Eid al-Fitr (announced by sighting)",
        "2025-03-31": "إجازة عيد الفطر Eid al-Fitr break",
        "2025-04-01": "إجازة عيد الفطر Eid al-Fitr break",
        "2025-06-05": "يوم عرفة Day of Arafat",
        "2025-06-06": "عيد الأضحى Eid al-Adha",
        "2025-06-09": "إجازة عيد الأضحى Eid al-Adha break",
        "2025-06-26": "رأس السنة الهجرية Islamic New Year (1447)",
        "2025-09-05": "المولد النبوي Prophet's Birthday",
        "2025-12-01": "يوم الشهيد Commemoration Day",
        "2025-12-02": "اليوم الوطني UAE National Day",
        "2025-12-03": "اليوم الوطني UAE National Day (second day)",
    },
    2026: {
        "2026-01-01": "رأس السنة الميلادية New Year's Day",
        "2026-03-19": "إجازة عيد الفطر Eid al-Fitr break begins (ESTIMATE)",
        "2026-03-20": "عيد الفطر Eid al-Fitr (1 Shawwal 1447, ASTRONOMICAL ESTIMATE)",
        "2026-03-23": "إجازة عيد الفطر Eid al-Fitr break (ESTIMATE)",
        "2026-05-26": "يوم عرفة Day of Arafat (ESTIMATE)",
        "2026-05-27": "عيد الأضحى Eid al-Adha (ASTRONOMICAL ESTIMATE)",
        "2026-05-28": "إجازة عيد الأضحى Eid al-Adha break (ESTIMATE)",
        "2026-06-16": "رأس السنة الهجرية Islamic New Year 1448 (ESTIMATE)",
        "2026-08-25": "المولد النبوي Prophet's Birthday (ESTIMATE)",
        "2026-12-01": "يوم الشهيد Commemoration Day",
        "2026-12-02": "اليوم الوطني UAE National Day",
        "2026-12-03": "اليوم الوطني UAE National Day (second day)",
    },
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": (
        "UAE closures come from three layers. "
        "(1) GREGORIAN AND FIXED: 1 January (which Saudi Arabia does NOT observe), 1 December "
        "(يوم الشهيد Commemoration Day) and 2-3 December (اليوم الوطني National Day). "
        "(2) HIJRI AND SIGHTING-FIXED: عيد الفطر and عيد الأضحى with يوم عرفة, plus رأس السنة "
        "الهجرية (Islamic New Year) and المولد النبوي (the Prophet's Birthday) -- the last two "
        "are UAE holidays and are NOT Saudi ones, which is a real difference between the two "
        "closure tables and not a transcription error. "
        "(3) CABINET DISCRETION: the Cabinet announces the exact break each year, and it has "
        "moved holidays to create long weekends, which no rule predicts. "
        "THE RULE THIS PACK USES is the same as the Saudi one: the astronomical new moon gives a "
        "CANDIDATE, the sighting announcement gives the ACTUAL date, and any study anchored on "
        "Eid must use the announced date, allow +/-1 day, and state which it used. "
        "SEPARATELY AND MORE IMPORTANTLY: the WEEKEND itself changed on 2022-01-03 from "
        "Friday-Saturday to Saturday-Sunday. That is not a holiday rule, it is a session-"
        "definition change, and it invalidates any pooled UAE day-of-week study."),
    "authority": "UAE Cabinet holiday announcements, moon-sighting committee announcements, and "
                 "the DFM and ADX trading-holiday notices",
    "table": _AE_HOLIDAYS,
    "status": {
        2024: "ANNOUNCED",
        2025: "ANNOUNCED",
        2026: "PARTLY ESTIMATED -- the Gregorian rows (01-01, 12-01, 12-02, 12-03) are certain; "
              "every Hijri row is an ASTRONOMICAL ESTIMATE that the sighting and the Cabinet may "
              "move by a day or more",
    },
    "market_effect": (
        "Crude, gold and the dollar trade through every UAE closure. What changes is the flow: "
        "the Eid break halts Gulf bank settlement and port clearance for several days, which "
        "shows up in throughput the following week rather than in price during the break; and "
        "since 2022 a UAE closure no longer coincides with a Saudi one, so 'the Gulf is shut' is "
        "a statement that now needs a country attached to it."),
    "callable": "countries.ae.pack:holidays",
}


def holidays(year: int) -> dict[str, str]:
    """The UAE closure table for one year, `{"YYYY-MM-DD": name}`. `{}` if untabulated."""
    return holiday_table(HOLIDAYS_RULE, year)


#: The date the UAE working week changed. Everything session-shaped in this pack splits here.
WEEKEND_CHANGE = date(2022, 1, 3)


def trading_week_on(day: date) -> dict[str, Any]:
    """Which days were trading days in the UAE on `day`, and what the weekend was.

    Code, not a table, because the rule is a single step with a date. A session study that calls
    this gets the right week for its sample; one that assumes either week is wrong for half of any
    multi-year sample.
    """
    if day >= WEEKEND_CHANGE:
        return {"date": day.isoformat(), "regime": "mon_fri", "weekend": ("Saturday", "Sunday"),
                "trading_days": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday"),
                "since": WEEKEND_CHANGE.isoformat(),
                "note": "the UAE trades the global week; Saudi Arabia, Qatar and Kuwait do not"}
    return {"date": day.isoformat(), "regime": "sun_thu", "weekend": ("Friday", "Saturday"),
            "trading_days": ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"),
            "until": WEEKEND_CHANGE.isoformat(),
            "note": "before 2022-01-03 the UAE shared the Gulf week, so the Gulf-Sunday-lead "
                    "mechanism included it"}


CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("ae_trading_week_router",
          domain_ids=("ae_session_structure", "ae_regional_funding_gulf_risk"),
          kind="calendar",
          entry="countries.ae.pack:trading_week_on",
          cadence_s=86400.0,
          steerable=False,
          notes="A fixed cost. Every UAE session study must route through this before it bins a "
                "day of the week, because the answer changed on 2022-01-03 and a miner that "
                "assumes one regime produces a confident wrong seasonal for the other half of "
                "the sample."),
)


# --------------------------------------------------------------------------- Gulf sections
#: QATAR AND KUWAIT, AS SECTIONS. Neither has enough independent executable ground for a pack:
#: their currencies are not quoted here, their equity indices are not quoted here, and their
#: transmission is through the same funding, energy and risk channels the UAE already owns. What
#: they DO have is distinct mechanics worth naming, and one of them -- the Kuwaiti basket peg --
#: is the only endogenous FX price in the GCC.
GULF_SECTIONS: dict[str, dict[str, Any]] = {
    "qa": {
        "name": "Qatar",
        "native_name": "دولة قطر",
        "currency": "QAR",
        "central_bank": "Qatar Central Bank (مصرف قطر المركزي); the QAR has been pegged at 3.64 "
                        "to the dollar since 2001, so QCB policy follows the Fed exactly as SAMA "
                        "and the CBUAE do",
        "exchange": "Qatar Stock Exchange (QSE), SUNDAY TO THURSDAY -- Qatar did NOT follow the "
                    "UAE's 2022 weekend change",
        "what_makes_it_different": (
            "Qatar is an LNG economy, not a crude one. The North Field expansion is the largest "
            "LNG capacity addition in the world, and most Qatari LNG is sold under LONG-TERM "
            "OIL-INDEXED CONTRACTS rather than at spot. So Qatari gas revenue follows BRENT with "
            "a three-to-six-month lag, and a study that links Qatar to the TTF or Henry Hub spot "
            "price is linking it to a market it largely does not sell into."),
        "observables": ("QCB monetary statistics and the QIBOR fixing",
                        "the QSE index and its weekly foreign-flow file",
                        "LNG loadings and long-term contract announcements",
                        "the Qatar Investment Authority's disclosed foreign holdings"),
        "policy_eras": ("2017-06 to 2021-01: the GCC blockade -- a genuine natural experiment in "
                        "regional risk pricing, with Qatari funding costs and the QAR forward "
                        "market dislocating while the peg held",
                        "2022-2023: the Ukraine gas shock made Qatari LNG geopolitically central "
                        "and lifted the oil-indexed revenue with a lag",
                        "2024 onward: North Field volumes begin to arrive"),
        "executable_carriers": ("XNGUSD", "XBRUSD", "XAUUSD", "US500"),
        "falsifier": "Qatari revenue stops tracking lagged Brent for three consecutive years, "
                     "which would mean the contract mix has genuinely moved to spot",
    },
    "kw": {
        "name": "Kuwait",
        "native_name": "دولة الكويت",
        "currency": "KWD",
        "central_bank": "Central Bank of Kuwait (بنك الكويت المركزي). THE EXCEPTION IN THE GULF: "
                        "since May 2007 the dinar is pegged to an UNDISCLOSED WEIGHTED BASKET of "
                        "currencies, not to the dollar alone. It was a pure dollar peg from 2003 "
                        "to 2007, and 2007 is therefore a hard regime boundary. Because the "
                        "basket is undisclosed, the CBK has genuine discretion and has NOT "
                        "matched every Fed move -- it is the one GCC policy rate that carries "
                        "information of its own.",
        "exchange": "Boursa Kuwait, SUNDAY TO THURSDAY; promoted to MSCI Emerging Markets in 2020, "
                    "which was a dated passive inflow",
        "what_makes_it_different": (
            "Two things. First, the basket peg makes the KWD the only GCC currency whose value is "
            "not mechanically the dollar's -- its drift against the dollar is a READ ON THE "
            "BASKET, which is a free, if noisy, estimate of how the region's largest reserve "
            "managers weight the euro and the yen. Second, the Future Generations Fund receives a "
            "fixed statutory share of state revenue every year, so Kuwait's sovereign accumulation "
            "is MECHANICAL and procyclical with oil in a way no other Gulf fund's is."),
        "observables": ("the CBK discount rate, which does NOT always follow the Fed",
                        "the KWD's drift against the dollar as a basket read",
                        "Kuwait Investment Authority disclosures and the statutory transfer",
                        "Boursa Kuwait foreign-flow files"),
        "policy_eras": ("2003-2007: a pure dollar peg",
                        "2007-05 onward: the undisclosed basket",
                        "2020: MSCI EM promotion, a dated passive inflow"),
        "executable_carriers": ("XBRUSD", "XAUUSD", "USDX", "EURUSD"),
        "falsifier": "the KWD's drift against the dollar shows no relationship to EURUSD and "
                     "USDJPY over a five-year window, which would mean the basket is a dollar peg "
                     "in all but name",
    },
}


# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"id": "cot_absent_aed",
     "name": "CFTC Commitments of Traders -- DECLARED ABSENT for the dirham",
     "covers": "nothing: there is no AED futures contract, and none for QAR, KWD, OMR or BHD "
               "either",
     "frequency": "n/a", "lag": "n/a", "root": "cftc.gov", "licence": "free, public",
     "note": "DECLARED BY NAME so no study reaches for 'speculative dirham positioning'. The COT "
             "series that matter to this pack are the CRUDE and NATURAL GAS ones, plus the DOLLAR "
             "INDEX, and those come from the desk's existing cot axis."},
    {"id": "dfm_adx_foreign_flows",
     "name": "DFM and ADX investor-type and nationality trading files",
     "covers": "daily and weekly net purchase by investor nationality and type",
     "frequency": "daily to weekly", "lag": "same day to a few days",
     "root": "dfm.ae, adx.ae", "licence": "free, public",
     "note": "Used as a GULF RISK STATE input. Since the 2021-2023 IPO wave and the foreign-"
             "ownership liberalisation, the composition of this flow changed structurally and a "
             "pooled series spans two different markets."},
    {"id": "fujairah_weekly_stocks",
     "name": "Fujairah oil product stockpiles",
     "covers": "light distillates, middle distillates and heavy residues at the Fujairah storage "
               "and bunkering complex",
     "frequency": "weekly", "lag": "days", "root": "fujairahoilindustryzone.com and the public "
                                                   "weekly distribution",
     "licence": "publicly distributed weekly; check the redistribution terms before storing bulk "
                "history",
     "note": "The region's best high-frequency PHYSICAL energy observable, and it sits on the "
             "Indian Ocean side of Hormuz -- which is exactly why it is informative about transit "
             "risk rather than only about demand."},
    {"id": "port_throughput",
     "name": "Jebel Ali and DP World throughput, and Khalifa Port volumes",
     "covers": "container throughput in TEU, quarterly and annually",
     "frequency": "quarterly", "lag": "weeks",
     "root": "dpworld.com investor disclosures", "licence": "public investor material",
     "note": "A WORLD TRADE sensor because Dubai re-exports; read as a global-demand state, never "
             "as a UAE domestic one, and never as an equity story about the operator."},
    {"id": "gulf_credit_licensed",
     "name": "Gulf sovereign and bank CDS levels",
     "covers": "regional credit risk",
     "frequency": "daily", "lag": "none", "root": "(commercial vendors)",
     "licence": "LICENSED -- named here and NEVER fetched",
     "note": "Catalogued so the gap is visible: the desk has no regional credit series, so every "
             "'Gulf risk premium' claim that needs one is UNMEASURED by name rather than proxied "
             "quietly."},
)


# --------------------------------------------------------------------------- terminology
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "core": ("الدرهم الإماراتي", "ربط الدرهم", "سعر الصرف", "المصرف المركزي", "سعر الفائدة",
             "إيبور", "السيولة", "الودائع", "الاحتياطي", "الدولار"),
    "ae_policy_peg": ("سعر الفائدة الأساسي", "تسهيلات الإيداع لليلة واحدة", "شهادات الإيداع",
                      "أذونات نقدية", "ربط الدرهم", "المصرف المركزي", "السياسة النقدية",
                      "الاحتياطي الفيدرالي", "خفض الفائدة", "رفع الفائدة"),
    "ae_funding_liquidity": ("إيبور", "سعر الفائدة بين البنوك", "السيولة المصرفية",
                             "نسبة الأصول السائلة", "الودائع المصرفية", "نمو الودائع",
                             "الائتمان المصرفي", "القروض", "شح السيولة", "فائض السيولة"),
    "ae_trade_shipping": ("جبل علي", "موانئ دبي العالمية", "إعادة التصدير", "التجارة الخارجية",
                          "الحاويات", "الشحن", "الفجيرة", "التموين بالوقود", "الخزانات",
                          "خط الأنابيب", "ميناء خليفة"),
    "ae_energy": ("أدنوك", "خام مربان", "العقود الآجلة", "إنتاج النفط", "الطاقة الإنتاجية",
                  "الغاز الطبيعي", "المصافي", "المشتقات النفطية", "المخزونات", "أوبك+"),
    "ae_gold_hub": ("الذهب", "سوق الذهب", "دبي للسلع المتعددة", "إعادة تصدير الذهب",
                    "الطلب على الذهب", "سبائك", "المشغولات الذهبية", "العلاوة السعرية"),
    "ae_sovereign_flow": ("جهاز أبوظبي للاستثمار", "مبادلة", "القابضة", "الصناديق السيادية",
                          "الاستثمارات الخارجية", "التحويلات المالية", "تحويلات العمالة"),
    "ae_equity_market": ("سوق دبي المالي", "سوق أبوظبي للأوراق المالية", "المؤشر العام",
                         "الاكتتابات", "الطروحات", "الملكية الأجنبية", "صافي شراء الأجانب",
                         "التداولات"),
    "ae_macro": ("التضخم", "أسعار المستهلك", "الناتج المحلي", "النمو غير النفطي",
                 "مؤشر مديري المشتريات", "السياحة", "العقارات", "أسعار الإيجارات",
                 "ضريبة القيمة المضافة"),
    "ae_session_structure": ("أيام العمل", "عطلة نهاية الأسبوع", "الجمعة", "السبت", "الأحد",
                             "ساعات التداول", "جلسة التداول", "الافتتاح", "الإغلاق"),
    "ae_gulf_risk": ("مضيق هرمز", "الملاحة البحرية", "التأمين البحري", "التوترات الإقليمية",
                     "الناقلات", "الهجمات", "المخاطر الجيوسياسية", "باب المندب"),
    "ae_hijri_calendar": ("رمضان", "عيد الفطر", "عيد الأضحى", "المولد النبوي",
                          "رأس السنة الهجرية", "يوم الشهيد", "اليوم الوطني", "إجازة رسمية"),
    "gulf_neighbours": ("قطر", "الكويت", "مصرف قطر المركزي", "بنك الكويت المركزي",
                        "الغاز المسال", "حقل الشمال", "سلة العملات", "الدينار الكويتي",
                        "الريال القطري", "بورصة الكويت"),
}


# --------------------------------------------------------------------------- source classes
#: THE TEN LAYERS, from the anchor pack. The depth rule (principal, 2026-09-17) is a Middle East
#: standing order, not a Saudi one: every source carries exactly one layer and three independent
#: labels, every layer is either sourced or declared ABSENT WITH A REASON, and every query below
#: is the ARABIC a crawler actually types. `countries.sa.pack` owns the builder and the validator
#: so the three packs cannot drift apart on the rule that binds all of them.
SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    me_source("ae_official_cb", "Central Bank of the UAE: statistics, bulletins and the fixings",
              layer="official",
              roots=("centralbank.ae", "centralbank.ae/en/statistics",
                     "the monetary and banking statistical bulletin, the quarterly economic "
                     "review, and the EIBOR page"),
              languages=("ar", "en"),
              licence="free, public; an open-data key is named in data/secrets/mena_apis.json and "
                      "never printed",
              access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
              queries=("إيبور اليوم", "النشرة الإحصائية الشهرية مصرف الإمارات",
                       "المعروض النقدي الإمارات", "الودائع المصرفية", "أذونات نقدية",
                       "سعر الفائدة الأساسي", "ميزان المدفوعات"),
              notes="Owns the whole funding leg of this pack: the daily fixings, the aggregates, "
                    "the banking indicators that are the CONTROL for every spread claim, and the "
                    "quarterly external accounts."),
    me_source("ae_official_stats", "Federal and emirate statistics offices",
              layer="official",
              roots=("fcsc.gov.ae", "scad.gov.ae (Abu Dhabi)", "dsc.gov.ae (Dubai)",
                     "u.ae open data", "dubailand.gov.ae transaction registry"),
              languages=("ar", "en"), licence="free, public",
              access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
              queries=("الرقم القياسي لأسعار المستهلك الإمارات", "الناتج المحلي غير النفطي",
                       "التجارة الخارجية غير النفطية", "مؤشر أسعار العقارات",
                       "بيانات دائرة الأراضي والأملاك"),
              notes="Remember the RE-EXPORT problem: Dubai's trade figures double-count transit, "
                    "so throughput is the signal and the balance is not."),
    me_source("ae_official_gulf_neighbours", "Qatar and Kuwait official statistics",
              layer="official",
              roots=("qcb.gov.qa", "qsa.gov.qa", "cbk.gov.kw", "csb.gov.kw",
                     "boursakuwait.com.kw", "qe.com.qa"),
              languages=("ar", "en"), licence="free, public",
              access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
              queries=("سعر الخصم بنك الكويت المركزي", "سلة العملات الدينار",
                       "مصرف قطر المركزي النشرة الشهرية", "صادرات الغاز المسال",
                       "بورصة الكويت تداولات الأجانب"),
              notes="The roots behind GULF_SECTIONS. The Kuwaiti discount rate is the only GCC "
                    "policy rate that is not mechanically the Fed's, which is the one reason to "
                    "crawl a Kuwaiti central-bank page at all."),
    me_source("ae_institutional_exchange", "DFM, ADX, DGCX, IFAD and the securities regulator",
              layer="institutional",
              roots=("dfm.ae", "adx.ae", "dgcx.ae", "theice.com (IFAD Murban settlements)",
                     "sca.gov.ae"),
              languages=("ar", "en"),
              licence="free, public; exchange settlement history may carry redistribution terms "
                      "and is treated as LICENSED until they are read",
              access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
              predictive_state="UNTESTED",
              queries=("سوق دبي المالي تداولات الأجانب", "سوق أبوظبي للأوراق المالية التقرير "
                       "اليومي", "خام مربان الأسعار", "تقويم الإجازات سوق دبي المالي",
                       "الملكية الأجنبية في الشركات"),
              notes="IFAD is where Abu Dhabi's crude is actually priced, which makes it the "
                    "institutional source that matters most here."),
    me_source("ae_institutional_research", "Gulf research and the multilateral consolidators",
              layer="institutional",
              roots=("imf.org Article IV for the UAE and Qatar", "worldbank.org Gulf economic "
                     "updates", "zawya.com research summaries",
                     "public research PDFs from Emirates NBD and First Abu Dhabi Bank"),
              languages=("en", "ar"),
              licence="public research pages only; never a paywalled terminal, never a licensed "
                      "feed redistributed",
              access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
              predictive_state="NARRATIVE_FEATURE",
              queries=("تقرير المادة الرابعة الإمارات", "توقعات النمو الاقتصادي",
                       "تقرير الاستقرار المالي", "التوقعات الاقتصادية لدول الخليج"),
              notes="The IMF Article IV is the only place the UAE's accounts are consolidated "
                    "ACROSS emirates; no single national source does it."),
    me_source("ae_academic", "Gulf funding, trade and energy literature",
              layer="academic",
              roots=("papers.ssrn.com (Gulf peg, funding and trade literature)",
                     "erf.org.eg", "kapsarc.org", "public working papers from NYU Abu Dhabi and "
                     "the American University of Sharjah", "imf.org working papers"),
              languages=("en", "ar"),
              licence="mixed: working papers and abstracts free, journal full text often "
                      "licensed; never scrape a paywall",
              access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
              predictive_state="UNTESTED",
              queries=("سياسة سعر الصرف الدرهم", "تحويلات العمالة الوافدة دراسة",
                       "إعادة التصدير الاقتصاد الإماراتي", "GCC peg dollar funding",
                       "remittance outflows Gulf"),
              notes="The remittance literature is the one that matters here: the surge-on-"
                    "home-currency-weakness behaviour is documented, and it is why USDINR is in "
                    "this pack's executable list."),
    me_source("ae_practitioner", "Gulf market professionals writing in public",
              layer="practitioner",
              roots=("public LinkedIn posts by UAE treasury, trade-finance and shipping "
                     "professionals", "DIFC and ADGM public event and seminar material",
                     "public podcast and conference transcripts from Gulf capital-market events",
                     "bunker and shipping brokers' public market commentary"),
              languages=("en", "ar"),
              licence="public web; VERBATIM CLAIMS only, no personal data, no private groups",
              access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
              predictive_state="NARRATIVE_FEATURE", evidence_weight=0.4,
              queries=("أسعار الشحن البحري", "تأمين المخاطر الحربية", "سيولة الدرهم",
                       "تمويل التجارة", "أسعار وقود السفن الفجيرة"),
              notes="The bunker and trade-finance practitioners are the ones worth reading: they "
                    "describe a rerouting before any statistic shows it."),
    me_source("ae_retail_ecology", "The Gulf retail investor ecology, Arabic and expatriate",
              layer="retail_ecology",
              roots=("public X/Twitter Arabic hashtags for the two exchanges",
                     "public Telegram broadcast channels", "Gulf finance YouTube comment "
                     "sections", "South Asian expatriate remittance and gold forums in English "
                     "and Malayalam"),
              languages=("ar", "en"),
              licence="public web; VERBATIM CLAIMS only, no personal data, no private groups",
              access_label="PUBLIC_SOCIAL", credibility="FRINGE", predictive_state="UNTESTED",
              evidence_weight=0.2,
              queries=("#سوق_دبي_المالي", "#سوق_ابوظبي", "توصيات الأسهم", "سعر الذهب اليوم "
                       "في الإمارات", "أفضل وقت للتحويل", "سعر صرف الروبية اليوم"),
              notes="FRINGE AND KEPT. The expatriate remittance and gold chatter is the retail "
                    "surface of two mechanisms this pack takes seriously -- when to convert and "
                    "when to buy physical gold -- and a wrong claim there is still evidence about "
                    "the behaviour. Low weight, never dropped."),
    me_source("ae_app_ecosystem", "The UAE financial app surface",
              layer="app_ecosystem",
              roots=("public app-store listings and review corpora for UAE brokerage, remittance "
                     "and payment apps (exchange houses, bank trading apps, Aani instant "
                     "payments)", "publishers' own public release notes and status pages"),
              languages=("ar", "en"),
              licence="app-store terms forbid bulk machine extraction of listings and reviews",
              access_label="ACCESS_UNCLEAR", credibility="UNKNOWN", predictive_state="UNTESTED",
              machine_use_allowed=True, evidence_weight=0.3,
              queries=("تطبيق تحويل الأموال", "أعطال تطبيق البنك", "تحديث تطبيق التداول"),
              notes="REGISTERED AND NEVER SCRAPED. Remittance-app outages and fee changes are "
                    "dated events in the corridor this pack trades through USDINR, and the terms "
                    "forbid machine extraction -- so the row exists, machine_use_allowed is "
                    "False, and no crawler is pointed at it."),
    me_source("ae_media", "Gulf press and the state wire",
              layer="media",
              roots=("wam.ae (the state news agency: Cabinet decisions and official statements "
                     "land here first)", "alkhaleej.ae", "emaratalyoum.com", "gulfnews.com",
                     "arabianbusiness.com", "zawya.com"),
              languages=("ar", "en"),
              licence="public headlines and article text; several outlets forbid bulk text and "
                      "data mining in their terms -- those are registered and not crawled",
              access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
              predictive_state="NARRATIVE_FEATURE",
              queries=("وكالة أنباء الإمارات قرار مجلس الوزراء", "إجازة العيد القطاع الخاص",
                       "أسعار الفائدة المصرف المركزي", "حركة الحاويات جبل علي",
                       "مخزونات الفجيرة الأسبوعية"),
              notes="WAM is the PRIMARY TIMESTAMP for a UAE official announcement, including the "
                    "Cabinet's holiday decisions -- which this pack's calendar depends on."),
    me_source("ae_archive", "The archived record of a country that rewrites its pages",
              layer="archive",
              roots=("web.archive.org captures of centralbank.ae, dfm.ae and adx.ae",
                     "CBUAE annual report and quarterly review PDF archives",
                     "DP World investor-disclosure archives",
                     "captures of the 2017-2021 blockade-era Qatari and UAE pages"),
              languages=("ar", "en"), licence="public archive; respect each archive's terms",
              access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
              predictive_state="UNTESTED",
              queries=("التقرير السنوي المصرف المركزي", "أرشيف النشرة الإحصائية",
                       "قرار تغيير عطلة نهاية الأسبوع 2021"),
              notes="The archive is where the 2022 weekend change, the 2021 base-rate framework "
                    "change and the blockade-era pages still exist AS THEY WERE. Three regime "
                    "boundaries in this pack are only datable from captures."),
    me_source("ae_physical_economy", "Ports, tanks, cargoes and the gold souk",
              layer="physical_economy",
              roots=("dpworld.com throughput disclosures", "fujairahoilindustryzone.com weekly "
                     "stockpiles", "adnoc.ae public releases", "jodidb.org",
                     "dmcc.ae and the Dubai gold trade's public volume reporting"),
              languages=("en", "ar"), licence="free, public / publicly distributed weekly",
              access_label="PUBLIC", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
              queries=("مخزونات الفجيرة من المنتجات النفطية", "حركة الحاويات في جبل علي",
                       "صادرات الذهب من دبي", "إنتاج النفط الإماراتي", "سعة التخزين النفطي"),
              notes="The Fujairah weekly stockpile is the region's best public high-frequency "
                    "PHYSICAL series, and it sits outside the chokepoint -- which is why it reads "
                    "transit risk and not only demand."),
    me_source("ae_physical_licensed", "Licensed cargo tracking and regional credit",
              layer="physical_economy",
              roots=("(commercial cargo trackers and credit-data vendors -- named so the gap is "
                     "visible, never fetched)",),
              languages=("en",),
              licence="LICENSED; redistribution and machine extraction forbidden by the vendors' "
                      "terms",
              access_label="LICENSED", credibility="RELIABLE", predictive_state="UNTESTED",
              machine_use_allowed=True,
              refused_reason="the desk holds no subscription and the terms forbid extraction; the "
                             "row exists so that 'the desk has no Gulf credit series' is a "
                             "MEASURED gap rather than an unnoticed one",
              queries=("(none -- this row is never queried)",),
              notes="REGISTERED, NOT CRAWLED. Every Gulf-risk claim that needs a credit leg is "
                    "UNMEASURED by name because of this row."),
    me_source("ae_source_graph", "Who carries what first, and the code that names the endpoints",
              layer="source_graph",
              roots=("zawya.com and gulfbase.com as aggregators, and which primary source they "
                     "cite", "github.com repositories calling CBUAE, DFM or ADX endpoints and "
                     "SDMX clients", "Arabic Wikipedia and Wikidata entries for UAE, Qatari and "
                     "Kuwaiti institutions", "the citation graph around Gulf IMF papers"),
              languages=("ar", "en"),
              licence="per-source; repositories are per-repository licensed and never vendored "
                      "without one",
              access_label="PUBLIC", credibility="UNKNOWN", predictive_state="UNTESTED",
              evidence_weight=0.5,
              queries=("نقلا عن وام", "حسب بيانات المصرف المركزي", "CBUAE api github",
                       "SDMX client python", "DFM data api"),
              notes="SDMX client code is worth reading HERE even though the UAE lane is not SDMX: "
                    "the Israeli lane in this civilization speaks SDMX and the parse is shared."),
    me_source("ae_refused_crypto_and_private", "Grounds this pack refuses on purpose",
              layer="source_graph",
              roots=("(none -- this row records a refusal, and a refusal is a decision, not an "
                     "oversight)",),
              languages=("ar", "en"), licence="n/a",
              access_label="ACCESS_UNCLEAR", credibility="UNKNOWN", predictive_state="UNTESTED",
              machine_use_allowed=True, evidence_weight=0.0,
              refused_reason="crypto-exchange venues, feeds and order books are refused under the "
                             "MT5 universe mandate (2026-08-18) -- and the refusal is stated "
                             "EMPHATICALLY here because Dubai licenses crypto venues, the local "
                             "vocabulary is full of them, and this is the pack where the "
                             "temptation is nearest; licensed CDS and tanker redistribution is "
                             "refused; single-name Gulf equities are refused as statistical "
                             "hypothesis ground (two-lane order 2026-09-06); private messaging "
                             "groups are refused because they are not public sources",
              queries=("(none -- this row is never queried)",),
              notes="Recorded rather than omitted, so a later session can tell a refusal from an "
                    "oversight."),
)

#: Every layer is sourced for the Emirates, so nothing is declared absent here. The tuple is kept
#: rather than omitted because an empty declaration and a missing one are different statements.
ABSENT_LAYERS: tuple[dict[str, Any], ...] = ()


# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    dataset("cbuae_monetary_aggregates",
            source="CBUAE monetary and banking statistics",
            coverage="M0, M1, M2 and M3, currency issued, and the monetary base",
            frequency="monthly",
            publication_lag_days=35.0,
            revisions="restated into the quarterly review; both vintages are kept",
            licence="free, public (CBUAE terms)",
            history_from="2000-01",
            pit_feasible=True,
            assets=("XAUUSD", "USDX", "US500", "XBRUSD"),
            mechanism_families=("liquidity_state", "regional_funding", "petrodollar_recycling"),
            how_to_fetch="CBUAE statistics pages or its open-data endpoint; key named in "
                         "data/secrets/mena_apis.json"),
    dataset("cbuae_banking_indicators",
            source="CBUAE banking indicators",
            coverage="bank deposits, credit by sector, the loan-to-deposit ratio and the eligible "
                     "liquid asset ratio",
            frequency="monthly",
            publication_lag_days=35.0,
            revisions="minor",
            licence="free, public",
            history_from="2000-01",
            pit_feasible=True,
            assets=("XAUUSD", "USDX", "US500"),
            mechanism_families=("regional_funding", "credit_cycle", "funding_stress"),
            how_to_fetch="CBUAE statistics; THE control series for every EIBOR-spread claim"),
    dataset("cbuae_daily_liquidity",
            source="CBUAE daily liquidity indicators and benchmark fixings",
            coverage="EIBOR by tenor, DONIA where published, the Base Rate, and the outstanding "
                     "stock of monetary bills",
            frequency="daily",
            publication_lag_days=0.4,
            revisions="none once fixed",
            licence="free, public",
            history_from="2010-01",
            pit_feasible=True,
            assets=("XAUUSD", "USDX", "UST05Y", "UST10Y"),
            mechanism_families=("funding_stress", "policy_state", "peg_defence"),
            how_to_fetch="CBUAE EIBOR page and the monetary-operations release; published about "
                         "11:00 GST (07:00 UTC). DECLARED: DONIA's exact publication time is not "
                         "verified on this box"),
    dataset("cbuae_bop_external",
            source="CBUAE balance of payments and external accounts",
            coverage="the current account, the oil and non-oil trade split, remittance outflows "
                     "and the international investment position",
            frequency="quarterly",
            publication_lag_days=75.0,
            revisions="each release restates the year to date; VINTAGES MATTER",
            licence="free, public",
            history_from="2005-Q1",
            pit_feasible=True,
            assets=("XBRUSD", "USDX", "USDINR"),
            mechanism_families=("external_balance", "remittance_flow", "petrodollar_recycling"),
            how_to_fetch="CBUAE quarterly economic review and its statistical annex"),
    dataset("fujairah_oil_stocks_weekly",
            source="Fujairah Oil Industry Zone weekly stockpile report",
            coverage="light distillates, middle distillates and heavy residues in storage",
            frequency="weekly",
            publication_lag_days=2.0,
            revisions="none",
            licence="publicly distributed weekly; verify redistribution terms before bulk storage",
            history_from="2017-01",
            pit_feasible=True,
            assets=("XBRUSD", "XTIUSD", "XNGUSD"),
            mechanism_families=("physical_inventory", "shipping_state", "hormuz_risk"),
            how_to_fetch="the weekly public release, normally Wednesday; store the release "
                         "timestamp with the value"),
    dataset("dp_world_throughput",
            source="DP World container throughput disclosures",
            coverage="TEU handled at Jebel Ali and across the global portfolio",
            frequency="quarterly",
            publication_lag_days=30.0,
            revisions="rare",
            licence="public investor material",
            history_from="2010-Q1",
            pit_feasible=True,
            assets=("XBRUSD", "US500", "USDINR", "USDX"),
            mechanism_families=("trade_state", "global_demand", "shipping_state"),
            how_to_fetch="the operator's quarterly throughput release; read as a WORLD TRADE "
                         "state, never as an equity story about the operator"),
    dataset("uae_pmi_monthly",
            source="the monthly UAE purchasing managers index (a published survey)",
            coverage="headline PMI, new orders, output and employment for the non-oil economy",
            frequency="monthly",
            publication_lag_days=3.0,
            revisions="none",
            licence="the headline is public; the detailed series is a LICENSED product and is "
                    "never redistributed here",
            history_from="2010-01",
            pit_feasible=True,
            assets=("XBRUSD", "US500", "USDX"),
            mechanism_families=("activity_nowcast", "trade_state"),
            how_to_fetch="the public headline release on about the third working day; the "
                         "sub-indices are licensed and are NOT stored"),
    dataset("ifad_murban_futures",
            source="ICE Futures Abu Dhabi (IFAD) Murban settlement prices",
            coverage="the Murban futures curve -- the price at which Abu Dhabi actually sells",
            frequency="daily",
            publication_lag_days=0.4,
            revisions="none",
            licence="exchange settlement data; check the redistribution terms, and treat bulk "
                    "history as LICENSED until they are read",
            history_from="2021-03",
            pit_feasible=True,
            assets=("XBRUSD", "XTIUSD"),
            mechanism_families=("supply_state", "basis", "administered_price"),
            how_to_fetch="the exchange's public settlement page. History begins 2021-03-29 and "
                         "NOT EARLIER -- the contract did not exist, and a backfill that splices "
                         "the old official selling price onto it is splicing two different "
                         "instruments"),
    dataset("dfm_adx_foreign_flow",
            source="DFM and ADX investor nationality trading files",
            coverage="net purchase by investor nationality and type",
            frequency="daily",
            publication_lag_days=0.5,
            revisions="none",
            licence="free, public",
            history_from="2014-01",
            pit_feasible=True,
            assets=("US500", "NAS100", "XAUUSD"),
            mechanism_families=("gulf_risk_state", "foreign_flow", "risk_appetite"),
            how_to_fetch="the two exchanges' daily market reports; a GULF RISK STATE input only"),
    dataset("uae_cpi_gdp",
            source="Federal Competitiveness and Statistics Centre",
            coverage="consumer prices with the housing component, and non-oil GDP",
            frequency="monthly (CPI) and quarterly (GDP)",
            publication_lag_days=30.0,
            revisions="occasional rebasing; a rebase is a BREAK and is stored as one",
            licence="free, public",
            history_from="2008-01",
            pit_feasible=True,
            assets=("XAUUSD", "USDX"),
            mechanism_families=("inflation_state", "real_rate"),
            how_to_fetch="fcsc.gov.ae releases; the 2018 VAT introduction is a level step and is "
                         "dummied explicitly, never smoothed"),
    dataset("qatar_kuwait_official",
            source="Qatar Central Bank and Central Bank of Kuwait statistics",
            coverage="policy rates, monetary aggregates and the KWD's basket drift against the "
                     "dollar",
            frequency="monthly, with daily rate fixings",
            publication_lag_days=30.0,
            revisions="minor",
            licence="free, public",
            history_from="2005-01",
            pit_feasible=True,
            assets=("XNGUSD", "XBRUSD", "EURUSD", "USDX"),
            mechanism_families=("regional_funding", "basket_peg_read", "lng_revenue_lag"),
            how_to_fetch="qcb.gov.qa and cbk.gov.kw statistics pages; the Kuwaiti discount rate "
                         "is the only GCC policy rate that is not mechanically the Fed's"),
    dataset("gulf_credit_spreads_licensed",
            source="Gulf sovereign and bank credit default swap levels",
            coverage="regional credit risk",
            frequency="daily",
            publication_lag_days=1.0,
            revisions="n/a",
            licence="LICENSED -- catalogued to make the gap visible and never fetched",
            history_from="2008-01",
            pit_feasible=False,
            assets=("XAUUSD", "USDX"),
            mechanism_families=("gulf_risk_state", "funding_stress"),
            how_to_fetch="NOT AVAILABLE TO THIS DESK. pit_feasible is False and any Gulf-risk "
                         "claim that needs a credit leg is UNMEASURED by name rather than proxied"),
)


# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    actor("the CBUAE monetary-operations desk",
          holds="the dirham peg and the domestic liquidity stock",
          forced_to=("match the Fed's policy rate through the Base Rate on the deposit facility",
                     "meet dollar demand at 3.6725",
                     "drain or add liquidity through monetary bills"),
          when="within hours of every FOMC decision; M-Bill auctions on their own schedule",
          information=("the Fed's decision", "banking-system liquidity", "deposit flows"),
          constraints=("the peg is a stated commitment", "a published benchmark framework"),
          instruments=("the overnight deposit facility", "monetary bills", "FX at the peg"),
          counterparties=("UAE banks", "the Federal Reserve as the de facto anchor"),
          observables=("the Base Rate", "EIBOR by tenor", "the outstanding M-Bill stock"),
          impact="sets the region's dollar funding cost and therefore its carry",
          persistence="policy-driven and decades long",
          falsifier="three Base Rate moves with no corresponding Fed move and no funding stress",
          notes="The anchor of the regional-funding family."),
    actor("UAE commercial and Islamic banks",
          holds="a dirham deposit base against a loan book weighted to real estate, trade finance "
                "and government-related entities",
          forced_to=("fund trade finance in dollars",
                     "bid for deposits when the liquid-asset ratio tightens",
                     "contribute to EIBOR daily"),
          when="continuous; strain is visible monthly in deposits and the liquidity ratios",
          information=("their own deposit flows", "the M-Bill calendar",
                       "regional trade volumes"),
          constraints=("eligible liquid asset ratio", "large-exposure limits to government-"
                       "related entities", "the peg, which removes independent rate setting"),
          instruments=("interbank dirham funding", "dollar trade finance", "deposits"),
          counterparties=("the CBUAE", "each other", "regional corporates and traders"),
          observables=("EIBOR", "deposit growth", "the eligible liquid asset ratio"),
          impact="the EIBOR-SOFR spread, which is regional funding stress when deposits do not "
                 "explain it and is nothing when they do",
          persistence="cyclical with trade and real estate",
          falsifier="an EIBOR-SOFR widening with no deposit or liquidity-ratio move, twice running",
          notes="This actor is the CONTROL for every UAE funding-stress claim."),
    actor("the Abu Dhabi sovereign funds (ADIA, Mubadala, ADQ)",
          holds="one of the largest pools of foreign assets in the world",
          forced_to=("deploy the oil surplus into foreign assets",
                     "meet domestic capital calls from the emirate"),
          when="continuously, with size procyclical to the oil account",
          information=("the emirate's oil revenue", "global asset valuations"),
          constraints=("mandates and asset-allocation targets",
                       "limited public disclosure -- only US holdings are visible, and only "
                       "quarterly"),
          instruments=("global equities and bonds", "direct and private investments"),
          counterparties=("global markets", "the emirate"),
          observables=("13F filings for US holdings", "announced direct deals",
                       "the current-account surplus"),
          impact="a persistent global risk-asset bid whose SIZE is a function of oil two to four "
                 "quarters earlier",
          persistence="strategic and multi-decade",
          falsifier="disclosed holdings stop growing with the lagged oil surplus over three years",
          notes="A FLOW actor; its holdings are single names and none is ever a hypothesis here."),
    actor("the Abu Dhabi national oil producer",
          holds="the emirate's crude and gas production and the Murban export grade",
          forced_to=("price Murban through a FUTURES MARKET since March 2021 rather than by "
                     "administered differential",
                     "hold to the OPEC+ quota while expanding capacity"),
          when="continuously since 2021-03-29; capacity announcements are dated events",
          information=("its own production and cargo nominations", "Asian buying interest"),
          constraints=("the OPEC+ quota", "a stated capacity expansion target"),
          instruments=("Murban futures", "physical cargoes", "the Fujairah pipeline that bypasses "
                       "Hormuz"),
          counterparties=("Asian refiners", "the futures market"),
          observables=("Murban settlement prices and curve shape",
                       "the Murban-Brent differential", "quota compliance"),
          impact="a market-priced supply signal with a continuous timestamp, unlike Saudi "
                 "Arabia's monthly announcement",
          persistence="structural since the 2021 pricing change",
          falsifier="Murban's curve stops carrying information about Asian demand beyond Brent's "
                    "own over a three-year window",
          notes="A SENSOR. The company is never a docket symbol."),
    actor("the Jebel Ali re-export trader",
          holds="inventory in transit through the world's largest entrepot between Singapore and "
                "Rotterdam",
          forced_to=("move goods on a shipping schedule",
                     "reroute when Hormuz, the Red Sea or Suez becomes unusable",
                     "pay war-risk insurance when it rises"),
          when="continuously; disruptions are dated events",
          information=("freight rates", "insurance quotes", "port congestion"),
          constraints=("vessel availability", "insurance cost", "letter-of-credit terms"),
          instruments=("physical goods", "freight contracts", "trade finance"),
          counterparties=("shipping lines", "banks", "importers across the Indian Ocean rim"),
          observables=("container throughput", "freight indices",
                       "Fujairah bunkering volumes"),
          impact="a global-trade state that leads reported national trade data by weeks",
          persistence="structural while the entrepot model holds",
          falsifier="throughput stops correlating with global trade volumes over a three-year "
                    "window",
          notes="Read as a WORLD state, not a UAE one: Dubai re-exports, so the domestic reading "
                "is the wrong one."),
    actor("the Fujairah bunkering and storage complex",
          holds="oil product inventory outside the Strait of Hormuz",
          forced_to=("hold and turn over product stocks for marine fuel demand",
                     "absorb the rerouting when Hormuz transit risk rises"),
          when="weekly, and the stockpile is PUBLISHED weekly",
          information=("marine fuel demand", "arbitrage economics", "transit risk"),
          constraints=("tank capacity", "product specification changes such as the 2020 sulphur "
                       "cap"),
          instruments=("physical product stocks", "bunker sales"),
          counterparties=("shipping lines", "refiners", "traders"),
          observables=("the weekly stockpile by product class", "bunker sales volumes"),
          impact="a high-frequency physical read on regional supply, demand and transit risk",
          persistence="structural; the complex exists because Hormuz is a chokepoint",
          falsifier="the weekly stockpile shows no response to a Hormuz transit-risk episode in "
                    "three consecutive episodes",
          notes="The clearest link in the pack between geopolitical risk and a public number."),
    actor("the expatriate remitter in the Emirates",
          holds="dirham wages earned by a workforce that is about ninety per cent foreign",
          forced_to=("remit a stable share of wages monthly",
                     "remit more when the home currency weakens -- a documented, exploitable "
                     "behavioural response"),
          when="monthly around the payroll cycle, with festival peaks",
          information=("the dirham-rupee and dirham-peso rates", "home-country conditions"),
          constraints=("fee structures", "the Wages Protection System's payroll timing"),
          instruments=("retail remittance corridors", "the dollar leg beneath them"),
          counterparties=("exchange houses", "banks", "recipient economies"),
          observables=("CBUAE remittance outflows by corridor",
                       "exchange-house volume commentary"),
          impact="one of the world's largest remittance outflows, with a documented surge when "
                 "the rupee weakens -- which links USDINR to a Gulf flow",
          persistence="structural while the workforce composition holds",
          falsifier="the remittance-versus-rupee response disappears over a three-year window",
          notes="The reason USDINR is in this pack's executable list."),
    actor("the Dubai physical gold trade",
          holds="bullion and jewellery inventory in one of the world's largest gold entrepots",
          forced_to=("meet festival and wedding demand in the Indian and African corridors",
                     "arbitrage the local premium against London"),
          when="seasonal, on both Hijri and Indian festival calendars",
          information=("the local premium or discount", "import duty changes in India",
                       "the dollar gold price"),
          constraints=("import rules in destination markets", "the Dubai Good Delivery standard"),
          instruments=("physical bullion", "jewellery", "re-exports"),
          counterparties=("Indian and African importers", "London and Swiss refiners"),
          observables=("the local physical premium", "gold re-export volumes",
                       "destination-market duty announcements"),
          impact="physical demand that supports or caps the dollar gold price at the margin",
          persistence="structural and seasonal",
          falsifier="the local premium stops carrying any information about gold's subsequent "
                    "path over a three-year sample",
          notes="A genuine XAUUSD observable that has nothing to do with the futures market."),
    actor("the Gulf risk-premium payer",
          holds="regional assets exposed to a geopolitical shock",
          forced_to=("pay up for protection when transit or conflict risk rises",
                     "reprice regional credit and equities before global markets do"),
          when="event-driven, and often while the desk's tape is closed",
          information=("regional news wires in Arabic", "insurance and freight quotes"),
          constraints=("thin regional markets", "limited hedging instruments"),
          instruments=("regional equities and credit", "war-risk insurance", "freight"),
          counterparties=("global macro investors", "insurers"),
          observables=("the Gulf equity indices' own session",
                       "war-risk insurance commentary", "regional credit spreads, which the desk "
                       "does NOT hold"),
          impact="a first read on a regional shock that arrives before the desk's own instruments "
                 "reopen",
          persistence="episodic but repeatable",
          falsifier="three consecutive regional shocks in which the Gulf session carries no "
                    "information about the subsequent global open",
          notes="Since 2022 this session means Saudi Arabia, Qatar and Kuwait -- not the UAE."),
    actor("the property developer and the mortgage borrower",
          holds="a real-estate cycle that dominates domestic credit",
          forced_to=("fund construction through bank credit",
                     "refinance when rates imported from the Fed rise"),
          when="continuous, with a pronounced multi-year cycle",
          information=("transaction registries, which Dubai publishes in detail",
                       "rental yields", "the imported policy rate"),
          constraints=("loan-to-value limits", "the peg, which imports the Fed's rate whatever "
                       "the local cycle needs"),
          instruments=("bank credit", "off-plan sales", "mortgages"),
          counterparties=("banks", "foreign buyers"),
          observables=("Dubai land-department transaction volumes",
                       "credit to the real-estate sector", "rental price indices"),
          impact="the domestic credit cycle and, through deposits, the funding-stress control",
          persistence="a long cycle with documented booms and busts (2008-2011, 2014-2019, "
                      "2021-onward)",
          falsifier="real-estate credit growth stops leading deposit and liquidity-ratio moves",
          notes="Named because the peg makes this cycle procyclical with US policy rather than "
                "countercyclical, which is the mechanism that makes Gulf funding stress possible."),
    actor("the Qatari LNG seller",
          holds="the world's largest long-term LNG contract book",
          forced_to=("deliver on multi-decade contracts",
                     "price most volume against a LAGGED OIL INDEX rather than gas spot"),
          when="continuous delivery; contract and expansion announcements are dated events",
          information=("Asian and European demand", "the North Field expansion schedule"),
          constraints=("contract terms", "liquefaction capacity"),
          instruments=("LNG cargoes", "long-term oil-indexed contracts"),
          counterparties=("Asian and European utilities",),
          observables=("loadings", "contract announcements", "lagged Brent"),
          impact="Qatari revenue follows Brent with a three-to-six-month lag, so Qatar's fiscal "
                 "state is an OIL state even though the product is gas",
          persistence="structural while the contract mix holds",
          falsifier="Qatari revenue stops tracking lagged Brent for three consecutive years",
          notes="The GULF_SECTIONS Qatar entry in actor form; the mistake it prevents is linking "
                "Qatar to spot gas."),
    actor("the Kuwaiti basket manager",
          holds="a dinar pegged to an UNDISCLOSED weighted basket, and the region's oldest "
                "sovereign fund",
          forced_to=("hold the dinar against a basket whose weights are never published",
                     "transfer a statutory share of state revenue into the Future Generations "
                     "Fund every year, whatever the oil price"),
          when="continuous; the statutory transfer is annual and mechanical",
          information=("the basket's constituent rates", "oil revenue"),
          constraints=("the basket is undisclosed, which is itself the policy",
                       "a statutory transfer that cannot be waived quietly"),
          instruments=("the dinar's managed rate", "sovereign-fund deployment"),
          counterparties=("the currency market", "global asset markets"),
          observables=("the KWD's drift against the dollar, which is a READ ON THE BASKET",
                       "the CBK discount rate, which does not always follow the Fed",
                       "the statutory transfer"),
          impact="the only endogenous FX price in the GCC, and a mechanical, procyclical sovereign "
                 "bid on global assets",
          persistence="structural since May 2007",
          falsifier="the dinar's drift shows no relationship to EURUSD and USDJPY over five years",
          notes="The GULF_SECTIONS Kuwait entry in actor form."),
)


# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    domain("ae_usd_liquidity_funding", "EIBOR, the base rate and regional dollar funding",
           objects=("EIBOR by tenor", "EIBOR minus the dollar curve", "the M-Bill stock",
                    "the Base Rate against the Fed's IORB"),
           conditions=("deposit growth", "the eligible liquid asset ratio",
                       "the June 2021 framework change"),
           instruments=("XAUUSD", "USDX", "UST05Y", "UST10Y"),
           controls=("deposit growth as the FIRST control -- a widening it explains is not stress",
                     "SAIBOR against the same dollar curve, since Saudi Arabia shares the peg",
                     "a matched calm-period window",
                     "the pre-June-2021 framework excluded rather than pooled"),
           notes="The regional-funding family's home domain."),
    domain("ae_regional_funding_gulf_risk", "A Gulf risk state built from funding and flow",
           objects=("the EIBOR-SOFR spread", "Gulf equity session returns",
                    "foreign-flow files from DFM and ADX", "Qatari and Kuwaiti policy rates"),
           conditions=("the oil regime", "the global risk regime",
                       "whether the event lands out of hours"),
           instruments=("XAUUSD", "US500", "NAS100", "USDX"),
           controls=("a global risk factor partialled out first, so a worldwide move is not read "
                     "as a Gulf one",
                     "matched non-event windows",
                     "a placebo on an instrument with no Gulf exposure"),
           notes="The state is the output; no Gulf instrument is ever the target."),
    domain("ae_trade_shipping_throughput", "Jebel Ali, Fujairah and the trade state",
           objects=("container throughput", "Fujairah weekly stockpiles", "bunker volumes",
                    "freight and war-risk insurance commentary"),
           conditions=("Red Sea and Suez routing", "Hormuz transit risk",
                       "the global inventory cycle"),
           instruments=("XBRUSD", "XTIUSD", "XNGUSD", "USDINR", "US500"),
           controls=("global freight indices as the common factor",
                     "matched non-disruption periods",
                     "a placebo on a non-trade-sensitive instrument"),
           notes="Re-export means this is a WORLD trade state; reading it as a UAE domestic one "
                 "is the standard mistake."),
    domain("ae_hormuz_transit_risk", "The chokepoint, and the pipeline that exists to bypass it",
           objects=("Hormuz transit-risk episodes", "the Fujairah pipeline's utilisation",
                    "war-risk insurance", "the Fujairah stockpile response"),
           conditions=("spare capacity", "the inventory regime",
                       "whether an episode is a threat or an actual interruption"),
           instruments=("XBRUSD", "XTIUSD", "XNGUSD", "XAUUSD", "USDJPY"),
           controls=("matched non-event windows in the same spare-capacity regime",
                     "the decay profile of prior episodes",
                     "a placebo on a non-energy instrument"),
           notes="The persistence question is the question: threats decay fast, interruptions do "
                 "not, and pooling them is what makes the literature look unstable."),
    domain("ae_peg_stability", "The dirham peg, and what repricing it would actually look like",
           objects=("the Base Rate against IORB", "EIBOR against SOFR",
                    "forward points where public", "commentary vocabulary"),
           conditions=("the oil regime", "regional credit conditions",
                       "the banking system's liquidity"),
           instruments=("XAUUSD", "USDX"),
           controls=("the Saudi peg observables as the sibling control",
                     "deposits and the liquidity ratio",
                     "a matched calm window"),
           notes="Forward points are NOT_PIT_SAFE here for the same reason as the riyal's, and "
                 "the pack says so rather than assuming an archive."),
    domain("ae_sovereign_recycling", "Sovereign funds as a lagged function of the oil account",
           objects=("disclosed US holdings", "announced direct deals",
                    "the current-account surplus", "Kuwait's statutory transfer"),
           conditions=("the oil price two to four quarters earlier", "global valuations"),
           instruments=("US500", "NAS100", "XAUUSD", "UST10Y"),
           controls=("global equity flows as the common factor",
                     "the oil price partialled out",
                     "quarters with no announced deal"),
           notes="Disclosure is partial and quarterly, so this domain's ceiling is a REGIME "
                 "reading and never a trigger."),
    domain("ae_remittance_corridor", "A Gulf wage bill as an emerging-market FX flow",
           objects=("CBUAE remittance outflows by corridor",
                    "the documented surge when the rupee weakens", "payroll timing"),
           conditions=("the home currency's level", "festival calendars",
                       "fee and regulation changes"),
           instruments=("USDINR", "USDX"),
           controls=("the rupee's own momentum partialled out",
                     "non-festival months matched by season",
                     "a placebo corridor with no Gulf exposure"),
           notes="The mechanism is behavioural and documented: remitters send more when the home "
                 "currency is weak, which makes the flow a stabiliser rather than a trend "
                 "follower."),
    domain("ae_gold_entrepot", "Dubai's physical gold trade as an XAUUSD observable",
           objects=("the local physical premium or discount", "re-export volumes",
                    "destination-market duty changes", "festival demand windows"),
           conditions=("the Indian import-duty regime", "Hijri and Indian festival calendars",
                       "the dollar gold price level"),
           instruments=("XAUUSD", "XAGUSD"),
           controls=("the dollar gold price's own momentum",
                     "non-festival windows matched by season",
                     "a placebo on a non-precious instrument"),
           notes="Physical premium is a demand observable that owes nothing to positioning, which "
                 "is exactly why it is worth having next to COT."),
    domain("ae_session_structure", "The 2022 weekend change and what it did to every session study",
           objects=("the UAE trading week before and after 2022-01-03",
                    "the divergence from the Saudi, Qatari and Kuwaiti week",
                    "day-of-week effects estimated on each side"),
           conditions=("the date relative to 2022-01-03", "the Hijri calendar",
                       "global holiday overlap"),
           instruments=("XBRUSD", "XAUUSD", "US500", "USDX"),
           controls=("the pre-change and post-change samples estimated SEPARATELY, never pooled",
                     "the Saudi week as the unchanged control",
                     "a placebo day-of-week test on an instrument with no Gulf exposure"),
           notes="This domain exists to stop a silent error rather than to find an edge, and that "
                 "is a legitimate reason for a domain to exist."),
    domain("ae_murban_pricing_regime", "A futures-priced crude versus an administered one",
           objects=("Murban settlements and curve shape", "the Murban-Brent differential",
                    "the March 2021 pricing change"),
           conditions=("the OPEC+ quota regime", "Asian demand",
                       "the date relative to 2021-03-29"),
           instruments=("XBRUSD", "XTIUSD"),
           controls=("Brent's own curve partialled out",
                     "the pre-2021 period EXCLUDED, never spliced",
                     "the Saudi official selling price as the administered-price comparison"),
           notes="A UAE supply study and a Saudi one are different event types; this domain keeps "
                 "them apart."),
    domain("ae_qatar_lng_lag", "Qatari LNG revenue as a lagged oil state",
           objects=("Qatari LNG loadings and contract announcements",
                    "lagged Brent", "the North Field expansion schedule"),
           conditions=("the contract mix", "European and Asian gas demand",
                       "the 2017-2021 blockade era"),
           instruments=("XNGUSD", "XBRUSD", "XAUUSD"),
           controls=("spot gas prices as the WRONG-benchmark control, included precisely to show "
                     "it is the wrong one",
                     "the blockade era split out",
                     "matched non-announcement windows"),
           notes="From GULF_SECTIONS. The error this prevents -- pricing Qatar off spot gas -- is "
                 "one a fast miner makes by default."),
    domain("ae_kuwait_basket_read", "The dinar's drift as a free read on reserve-manager weights",
           objects=("the KWD's drift against the dollar", "the CBK discount rate",
                    "the statutory sovereign transfer"),
           conditions=("the post-2007 basket regime only", "the oil regime",
                       "global dollar moves"),
           instruments=("EURUSD", "USDJPY", "USDX", "XAUUSD"),
           controls=("the pre-2007 dollar-peg period EXCLUDED",
                     "the dollar index's own move partialled out",
                     "a placebo on a floating EM currency"),
           notes="From GULF_SECTIONS. A small, noisy signal with a real mechanism: the basket is "
                 "undisclosed, so its drift is the only public estimate of the weights."),
)


# --------------------------------------------------------------------------- transmission seeds
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("ae_eibor_spread_to_dollar",
         source="3M EIBOR minus the 3M dollar curve, residualised on deposit growth",
         mechanism="dollar scarcity in the region that runs the largest external surplus is a "
                   "statement about global dollar funding, not about the dirham",
         targets=("USDX", "XAUUSD"),
         sign="a widening that survives the deposit control -> dollar-supportive and gold-"
              "supportive together, the signature of funding stress",
         horizon="2 weeks to 2 months",
         lag="1 day",
         control="deposit growth and the liquid-asset ratio FIRST; SAIBOR as the sibling peg",
         evidence="HYPOTHESIS"),
    edge("ae_liquidity_to_global_risk",
         source="UAE M3 and bank deposit growth, plus the outstanding M-Bill stock",
         mechanism="regional liquidity is the petrodollar's near leg: when the Gulf's banks are "
                   "flush, the recycling into global assets is larger and faster",
         targets=("US500", "NAS100", "XAUUSD"),
         sign="accelerating liquidity -> supportive for global risk",
         horizon="1 to 6 months",
         lag="35 days",
         control="US liquidity measures as the common factor; Saudi M3 as the regional sibling",
         evidence="HYPOTHESIS"),
    edge("ae_throughput_to_global_demand",
         source="Jebel Ali and DP World container throughput growth",
         mechanism="an entrepot's volume is world trade passing through a single measurable point, "
                   "weeks before national trade statistics exist",
         targets=("US500", "XBRUSD", "USDINR", "USDX"),
         sign="accelerating throughput -> supportive for global cyclical risk and for crude demand",
         horizon="1 to 2 quarters",
         lag="30 days",
         control="global freight indices partialled out; the re-export double-count acknowledged "
                 "explicitly",
         evidence="HYPOTHESIS"),
    edge("ae_fujairah_stocks_to_crude",
         source="the weekly Fujairah oil-product stockpile change by product class",
         mechanism="a physical inventory at the world's second bunkering hub, outside the "
                   "chokepoint, reads both regional supply and rerouting",
         targets=("XBRUSD", "XTIUSD"),
         sign="a sustained build in middle distillates -> demand weakness -> negative for crude",
         horizon="1 to 6 weeks",
         lag="2 days",
         control="global product inventories as the common factor; matched non-disruption weeks",
         evidence="HYPOTHESIS",
         notes="One of very few WEEKLY physical energy series in the region that is public."),
    edge("ae_hormuz_risk_to_energy_and_gold",
         source="a Hormuz or Red Sea transit-risk episode, timestamped",
         mechanism="a threat to the transit of roughly a fifth of seaborne oil is a supply-"
                   "convexity event; the Fujairah pipeline caps the tail and the market knows it",
         targets=("XBRUSD", "XTIUSD", "XNGUSD", "XAUUSD"),
         sign="episode -> crude and gold up together, crude decaying faster; a THREAT and an "
              "INTERRUPTION have different half-lives and are never pooled",
         horizon="1 to 15 sessions",
         lag="minutes to hours",
         control="matched non-event windows in the same spare-capacity regime; prior episodes' "
                 "decay profiles",
         evidence="MEASURED_ELSEWHERE"),
    edge("ae_remittance_to_usdinr",
         source="CBUAE remittance outflows, corridor split, against the rupee's level",
         mechanism="remitters send MORE when the home currency is weak, so the Gulf wage bill is "
                   "a countercyclical dollar supply into the rupee",
         targets=("USDINR",),
         sign="a rupee-weakness episode -> elevated remittance flow -> a stabilising bid for the "
              "rupee with a lag",
         horizon="1 to 3 months",
         lag="75 days for the quarterly series, which makes this a REGIME claim",
         control="the rupee's own momentum partialled out; non-festival months matched",
         evidence="MEASURED_ELSEWHERE",
         notes="The remittance-surge-on-weakness behaviour is documented in the public "
               "literature; the desk has not reproduced it and the seed says so."),
    edge("ae_gold_premium_to_xauusd",
         source="the Dubai physical gold premium or discount and re-export volumes",
         mechanism="physical demand in one of the world's largest entrepots supports or caps the "
                   "dollar price at the margin, independently of futures positioning",
         targets=("XAUUSD", "XAGUSD"),
         sign="a sustained physical premium -> supportive; a persistent discount -> the opposite",
         horizon="2 to 8 weeks",
         lag="days",
         control="gold's own momentum; COT positioning as the orthogonal factor; festival windows "
                 "matched",
         evidence="HYPOTHESIS"),
    edge("ae_murban_curve_to_brent",
         source="the Murban futures curve shape and the Murban-Brent differential, from "
                "2021-03-29 ONLY",
         mechanism="the price at which Abu Dhabi actually sells carries Asian demand information "
                   "that Brent, an Atlantic-basin benchmark, does not",
         targets=("XBRUSD", "XTIUSD"),
         sign="Murban backwardation steepening relative to Brent -> Asian demand firming -> "
              "supportive",
         horizon="1 to 20 sessions",
         lag="none",
         control="Brent's own curve partialled out; the pre-2021 period EXCLUDED, never spliced",
         evidence="HYPOTHESIS"),
    edge("ae_gulf_risk_to_risk_off",
         source="the Gulf risk state: regional session returns, funding spread and flow files",
         mechanism="a regional shock is priced in Gulf sessions that run when the desk's venue is "
                   "shut or thin, so the state leads the desk's own risk instruments",
         targets=("XAUUSD", "US500", "USDJPY"),
         sign="a deteriorating Gulf risk state -> risk-off in the desk's instruments",
         horizon="1 to 10 sessions",
         lag="hours to a day",
         control="a global risk factor partialled out FIRST; matched calm windows; a placebo "
                 "instrument",
         evidence="HYPOTHESIS",
         notes="Since 2022 the Gulf session in this edge is Saudi, Qatari and Kuwaiti -- the UAE "
               "trades the global week and is no longer part of the lead."),
    edge("ae_qatar_lng_lag_to_gas",
         source="lagged Brent and Qatari contract and expansion announcements",
         mechanism="most Qatari LNG is sold on oil-indexed long-term contracts, so Qatari revenue "
                   "and behaviour follow Brent with a three-to-six-month lag rather than gas spot",
         targets=("XNGUSD", "XBRUSD"),
         sign="a Brent regime change -> Qatari revenue and expansion behaviour change two "
              "quarters later",
         horizon="1 to 2 quarters",
         lag="90 to 180 days",
         control="spot gas included as the WRONG-benchmark control; the 2017-2021 blockade split "
                 "out",
         evidence="HYPOTHESIS"),
    edge("ae_kuwait_basket_to_majors",
         source="the KWD's drift against the dollar, post-2007 only",
         mechanism="the basket weights are undisclosed, so the dinar's drift is the only public "
                   "estimate of how a large reserve manager weights the euro and the yen",
         targets=("EURUSD", "USDJPY", "USDX"),
         sign="dinar strength against the dollar -> a basket tilt away from the dollar",
         horizon="1 to 3 months",
         lag="days",
         control="the dollar index's own move partialled out; the pre-2007 dollar-peg era excluded",
         evidence="HYPOTHESIS",
         notes="Small and noisy, and included because the mechanism is real and the alternative "
               "is pretending the GCC has no endogenous FX price at all."),
)


# --------------------------------------------------------------------------- policy eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    era("ae_pre_2015", start="2010-01-01", end="2014-12-31",
        label="post-crisis recovery and the hundred-dollar barrel",
        what_changed="Dubai's post-2009 debt restructuring completed; oil above breakeven; no "
                     "VAT; a Sunday-to-Thursday week",
        invalidates="pooling this with the post-2022 era mixes two working weeks, two tax regimes "
                    "and two oil regimes"),
    era("ae_2015_17_oil_shock_and_blockade", start="2015-01-01", end="2017-12-31",
        label="the oil shock and the start of the Qatar blockade",
        what_changed="the oil crash squeezed Gulf deposits and widened funding spreads across the "
                     "region; the GCC blockade of Qatar began in June 2017 and split the regional "
                     "funding market",
        invalidates="a 'Gulf' funding aggregate estimated across the blockade is averaging two "
                    "markets that were deliberately separated"),
    era("ae_2018_vat_and_framework", start="2018-01-01", end="2020-12-31",
        label="VAT, the pandemic and the monetary-bill programme",
        what_changed="VAT at 5% from 2018-01-01 (a level step, not inflation); the pandemic "
                     "collapsed throughput and travel and then rebounded them; monetary bills "
                     "(M-Bills) replaced Certificates of Deposit in 2020",
        invalidates="a liquidity study pooled across the M-Bill transition is pooling two "
                    "different drain instruments"),
    era("ae_2021_framework_and_murban", start="2021-01-01", end="2021-12-31",
        label="the ODF base rate, Murban futures and the end of the blockade",
        what_changed="the CBUAE moved its Base Rate to the Overnight Deposit Facility anchored to "
                     "IORB in June 2021; Murban futures launched on 2021-03-29, replacing the "
                     "retroactive official selling price; the Qatar blockade ended in January 2021",
        invalidates="THREE separate regime changes in one year. A policy, supply or regional-"
                    "funding series that crosses 2021 without splitting is averaging across all "
                    "three."),
    era("ae_2022_weekend_and_rate_cycle", start="2022-01-01", end="2023-12-31",
        label="the Monday-to-Friday week and the imported hiking cycle",
        what_changed="the working week changed on 2022-01-03; the Fed's hiking cycle was imported "
                     "wholesale through the peg; the energy shock lifted Gulf surpluses and "
                     "sovereign deployment; federal corporate tax was legislated for financial "
                     "years from 2023-06-01",
        invalidates="every day-of-week and session-overlap result for the UAE is defined "
                    "differently on each side of 2022-01-03, and the Gulf-Sunday-lead mechanism "
                    "loses the UAE as a member"),
    era("ae_2024_onward", start="2024-01-01", end=None,
        label="the easing cycle, corporate tax in force and the North Field's first volumes",
        what_changed="the Fed's easing imported through the peg from September 2024; corporate "
                     "tax in force; Qatari North Field capacity beginning to arrive; Red Sea "
                     "rerouting made Gulf trade routing a live variable again",
        invalidates="a trade or throughput model fitted before the Red Sea rerouting does not "
                    "describe the routing that followed it"),
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
    """The United Arab Emirates country pack, with the Qatar and Kuwait sections attached."""
    return build_pack(**FIELDS)


def instrument_report(path: Any = None) -> dict[str, Any]:
    """What this pack can trade, what carries its economics, and what is missing -- measured."""
    split = resolve(EXECUTABLE_INSTRUMENTS, path)
    return {"code": CODE, "own_price": OWN_PRICE, "executable": tuple(split["tradable"]),
            "equities_refused": tuple(split["equities"]),
            "absent_from_universe": tuple(split["absent"]),
            "transmission_targets": TRANSMISSION_TARGETS,
            "named_absent_instruments": ABSENT_INSTRUMENTS,
            "gulf_sections": tuple(GULF_SECTIONS),
            "dataset_fields": DATASET_FIELDS}
