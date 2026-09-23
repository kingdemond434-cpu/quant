"""HUNGARY -- six crosses, two policy rates and a conditionality switch, as DATA.

See `countries/hu/__init__.py` for why this country earns its own department. This module is the
pack itself: identity, conventions, calendars, actors, domains, sources, datasets, edges, eras,
cells and the department entry `mine()`. Nothing here is prose for a human to act on; everything
here is read by a miner or checked by a test.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "HU"
NAME = "Hungary"
#: THE PARITY FENCE COUNTS THIS. Declared rather than inferred from the directory name.
JURISDICTIONS: tuple[str, ...] = ("hu",)
REGION_COMMAND = "europe"
REGION_DESK = "CEE"
FOREST = "europe"
CURRENCY = "HUF"
FISCAL_YEAR_END = "12-31"          # the central budget runs on the calendar year
NATIVE_LANGUAGES: tuple[str, ...] = ("hu", "de", "en")
COT_CURRENCY = ""                  # no CFTC contract exists for the forint
EXPORT_ECONOMY = "manufacturing_exporter"      # vehicles, batteries and electronics
RETAIL_LEVERAGE_REGIME = "esma_capped"         # an EU member state: ESMA 30:1 major-FX cap
MISSION = ("mine Hungary as the six-cross, two-rate, politically-conditioned economy it is: the "
           "MNB's 18% one-day deposit emergency and its convergence back to the base rate, the "
           "FX swap tenders, the EU recovery-fund conditionality as a dated political event with "
           "a forced conversion behind it, the 2015 forint conversion that cut the CHF loop out "
           "of the forint's beta, the Druzhba exemption and the utility price cap, the AKK "
           "auction calendar and the KSH release clock -- and, because SIX HUF crosses are "
           "quoted here, decompose every move into the HUF common factor and the cross-specific "
           "residual instead of guessing which one it was")

#: The instruments this pack may compile a cell against. Every one is in the broker registry and
#: none is a single-name equity. SIX of them are HUF crosses, which is the widest single-currency
#: cross set the desk quotes and the structural reason this pack exists.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "EURHUF", "USDHUF", "AUDHUF", "CHFHUF", "GBPHUF", "NZDHUF",   # the six-cross panel
    "EURUSD",                                  # the leg that separates a forint move from a euro
    "EURPLN", "EURCZK",                        # the CEE peers: the regional factor's own null
    "GER40", "EUSTX50",                        # the German chain Hungarian industry feeds
    "XNGUSD", "XBRUSD",                        # the gas call and the Druzhba-exempt crude leg
    "XAUUSD",                                  # the MNB's 3.1t to 110t gold accumulation
)

#: EVERY INSTRUMENT THIS COUNTRY'S MECHANISMS RUN THROUGH THAT THE BROKER DOES NOT QUOTE.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "BUX and BUMIX (the Budapest Stock Exchange indices)",
     "venue": "Budapesti Ertektozsde (BET), majority-owned by the MNB since 2015",
     "why": "no CFD is quoted, and the index is four names -- OTP, MOL, Richter and Magyar "
            "Telekom -- so a BUX study is a single-name study wearing an index's hat, which the "
            "two-lane order forbids",
     "proxies": ("EUSTX50", "GER40", "EURHUF")},
    {"name": "Hungarian government bonds (allampapir) and the HUF swap curve",
     "venue": "AKK primary auctions; the interbank secondary market",
     "why": "the rate path the MNB's decision actually moves; absent from the broker, so the "
            "decision is read on the six HUF crosses and controlled with EURUSD",
     "proxies": ("EURHUF", "USDHUF", "EURPLN")},
    {"name": "BUBOR and the MNB's own instruments: the base rate, the one-week and the one-day "
             "deposit, the discount bond and the FX swap tender",
     "venue": "the MNB's tenders and the BUBOR panel",
     "why": "THE TWO-RATE REGIME lives here: for eleven months the effective rate and the base "
            "rate were different numbers, and the carry a HUF short paid was the higher one",
     "proxies": ("EURHUF", "USDHUF", "CHFHUF")},
    {"name": "MAP Plusz and the retail government securities programme",
     "venue": "AKK and the Magyar Allamkincstar retail network",
     "why": "an enormous household bond programme that competes with bank deposits and with "
            "the wholesale curve at once; it is a domestic funding channel with no instrument",
     "proxies": ("EURHUF", "EURPLN")},
    {"name": "HUDEX power and gas futures and the CEEGEX/MGP gas spot",
     "venue": "HUDEX Hungarian Derivative Energy Exchange; CEEGEX",
     "why": "Hungarian power and gas prices are not quoted here; the call on imported gas and "
            "the crude leg of the refining margin are",
     "proxies": ("XNGUSD", "XBRUSD", "GER40")},
    {"name": "The Urals-to-Brent discount on Druzhba pipeline crude",
     "venue": "assessed by price reporting agencies; not an exchange product",
     "why": "Hungary's pipeline-crude exemption from the EU import ban means its refiner buys "
            "at a discount other European refiners cannot; the discount itself is LICENSED "
            "assessment ground and the crude benchmark is executable",
     "proxies": ("XBRUSD", "XNGUSD")},
    {"name": "The household FX-loan stock, converted in 2015 at administratively fixed rates",
     "venue": "the banks' balance sheets; the MNB's conversion tenders",
     "why": "the channel this economy USED to have and no longer does; the conversion is a "
            "dated regime break in the CHFHUF relationship and not a tradable object",
     "proxies": ("CHFHUF", "EURHUF")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Magyar Nemzeti Bank -- Monetaris Tanacs",
    "short": "MNB",
    "framework": "inflation_targeting",
    "committee": "the Monetaris Tanacs: the Governor, the Deputy Governors and the members "
                 "elected by Parliament; the vote is not published as a named split",
    "policy_instrument": "the base rate (alapkamat) with an interest-rate corridor -- BUT the "
                         "EFFECTIVE instrument has repeatedly been something else: the one-week "
                         "deposit rate from 2020, and the ONE-DAY DEPOSIT QUICK TENDER from "
                         "2022-10-14, which stood at 18% while the base rate stood at 13%",
    "mandate": "price stability under the MNB Act, with a secondary mandate to support the "
               "government's economic policy and financial stability; the target is 3% with a "
               "+/-1pp tolerance band, so a surprise IS measurable against a published number",
    "decision_rule": "the Monetary Council meets on the LAST TUESDAY of the month for a rate "
                     "decision, announces in the early afternoon and holds a press conference "
                     "afterwards; a second, non-rate meeting is held mid-month",
    "decision_calendar_rule": "one rate-setting meeting a month, on the published calendar at "
                              "mnb.hu, plus the non-rate mid-month meeting. THE CLOCK BROKE "
                              "TWICE: the one-day deposit tender was decided DAILY outside this "
                              "calendar in 2022-2023, and the weekly one-week deposit tender "
                              "was the effective decision for periods in 2020-2022 -- so a "
                              "monthly event calendar is NOT a complete list of Hungarian "
                              "policy events and the pack says so",
    "decision_dates": (
        "2021-06-22", "2021-07-27", "2021-08-24", "2021-09-21", "2021-10-19", "2021-11-16",
        "2021-12-14",
        "2022-01-25", "2022-02-22", "2022-03-22", "2022-04-26", "2022-05-31", "2022-06-28",
        "2022-07-26", "2022-08-30", "2022-09-27",
        "2022-10-14",
        "2023-09-26", "2023-10-24", "2023-11-21", "2023-12-19",
        "2024-01-30", "2024-02-27", "2024-03-26", "2024-04-23", "2024-05-21", "2024-06-18",
        "2024-07-23", "2024-09-24", "2024-10-22", "2024-11-19", "2024-12-17"),
    "dates_status": "PRESS_REPORTED AND PARTIAL, deliberately. The 2021-2022 rows are the "
                    "hiking cycle's last-Tuesday meetings; 2022-10-14 is the EXTRAORDINARY day "
                    "the 18% one-day deposit tender was introduced and is NOT a Tuesday; the "
                    "2023-09-26 row is the meeting at which the one-day rate was merged back "
                    "into the base rate; the 2024 rows are the easing cycle. RE-VERIFY every "
                    "one against the mnb.hu decision archive before a cell is compiled on it. "
                    "2025 and 2026 are NOT LISTED: the MNB publishes the calendar and this pack "
                    "refuses to invent it (L1.28a)",
    "decision_time_utc": "13:00",
    "announce_local": "early afternoon Europe/Budapest on the meeting Tuesday (about 14:00 "
                      "local), with the press conference about an hour later; the exact minute "
                      "has moved over the years and must be stamped from the release, not "
                      "assumed",
    "dst_rule": "Europe/Budapest is CET (UTC+1) and CEST (UTC+2) on the EU rule, so the same "
                "local announcement lands at two different UTC minutes across the year",
    "minutes_lag_days": 14,
    "publication_classes": ("kamatdontes", "a_monetaris_tanacs_kozlemenye", "inflacios_jelentes",
                            "jegyzokonyv", "penzugyi_stabilitasi_jelentes", "devizatartalek",
                            "statisztikai_idosorok"),
    "policy_rate_series": "MNB:alapkamat",
    "expected_rate_series": "MNB:egynapos_betet",
    "consensus_proxy": "the BUBOR curve and the FRA market on the morning of the meeting, plus "
                       "the analyst consensus the domestic press polls and publishes",
    "consensus_proxy_trap": "BUBOR tracked the BASE rate while the EFFECTIVE rate was the "
                            "one-day deposit tender, so in 2022-2023 the 'consensus' and the "
                            "actual funding cost were different objects by up to five "
                            "percentage points -- a carry study that used the base rate was "
                            "measuring a rate nobody could fund at",
    "reserves_clock": "devizatartalek is published monthly, a few business days after the month "
                      "end; the 2014-2015 conversion tenders are a visible drawdown and the "
                      "gold accumulation is a visible series of steps",
    "programme": "no IMF programme since the 2008-2010 standby was repaid early in 2013; the "
                 "external conditionality here is EUROPEAN and political -- the rule-of-law "
                 "conditionality mechanism and the Recovery and Resilience Facility milestones "
                 "-- which is a different clock from an IMF review and is carried in HU-E",
    "off_cycle": ("2022-10-14 the one-day deposit quick tender introduced at 18% outside the "
                  "normal calendar",
                  "2023-05 onward the one-day rate cut in monthly steps back toward the base "
                  "rate", "2023-09-26 the two rates merged at 13%"),
    "root": "https://www.mnb.hu",
}
#: THE TWO-RATE REGIME, as dates a test can check. For eleven months "the Hungarian policy rate"
#: was two different numbers, and the one that mattered for funding was the higher one.
TWO_RATE_REGIME: dict[str, Any] = {
    "instrument": "the overnight (one-day) deposit quick tender, egynapos betéti gyorstender",
    "introduced": date(2022, 10, 14),
    "peak_rate_pct": 18.0,
    "base_rate_at_peak_pct": 13.0,
    "converged": date(2023, 9, 26),
    "convergence_rule": "cut in roughly monthly steps from May 2023 until the one-day rate met "
                        "the 13% base rate, at which point the instruments were merged",
    "status": "PRESS_REPORTED for the step dates and the intermediate levels; the two boundary "
              "dates are the ones this pack conditions on and they must be RE-VERIFIED against "
              "the MNB communique before a cell is compiled on them",
    "what_it_invalidates": (
        "any Hungarian carry, funding or rate-differential series built on the BASE RATE across "
        "2022-10-14..2023-09-26, which understates the real cost of a forint short by up to "
        "five percentage points",
        "any 'policy surprise' measured against a monthly meeting calendar in that window, "
        "because the effective rate was set at a DAILY tender outside the calendar",
        "any pooled event study of MNB decisions spanning the window, which mixes decisions "
        "about a rate that bound with decisions about a rate that did not",
        "any BUBOR-based estimate of Hungarian funding conditions in the window, since BUBOR "
        "tracked the base rate and not the tender"),
}
#: THE 2015 CONVERSION. A dated, administrative removal of a transmission channel.
FX_LOAN_CONVERSION: dict[str, Any] = {
    "name": "forintositas -- the conversion of household FX mortgages into forint",
    "announced": date(2014, 11, 7),
    "effective": date(2015, 2, 1),
    "mechanism": "household CHF- and EUR-denominated mortgages were converted at "
                 "administratively fixed rates, with the MNB supplying the foreign currency "
                 "from its own reserves so the conversion did not have to be bought in the "
                 "market",
    "status": "SETTLED as to the fact and the year; the exact fixed rates and the tender "
              "schedule are PRESS_REPORTED here and must be cited from the MNB before use",
    "what_it_removed": (
        "the household balance-sheet loop: before the conversion a CHF rally raised Hungarian "
        "mortgage payments directly, which fed back into the forint and into domestic demand",
        "the forced-deleveraging bid for CHF that appeared whenever CHFHUF rose",
        "a large part of the forint's sensitivity to Swiss monetary policy, which is why "
        "CHFHUF before 2015 and CHFHUF after 2015 are not the same relationship"),
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "MNB official forint exchange rates (hivatalos devizaárfolyam)",
     "local": "fixed at 11:00 Europe/Budapest on each working day and published shortly after",
     "time_utc": "10:00", "time_utc_dst": "09:00", "dst_rule": "CET/CEST on the EU rule",
     "instruments": ("EURHUF", "USDHUF", "CHFHUF"), "window_minutes": 30,
     "why": "the rate every Hungarian accounting entry, tax filing and administered conversion "
            "uses; it is a fixing with a published minute, which is a tradable clock"},
    {"name": "BUBOR fixing (the Budapest interbank reference rate)",
     "local": "10:30 Europe/Budapest, published by the MNB from the panel quotes",
     "time_utc": "09:30", "time_utc_dst": "08:30", "dst_rule": "CET/CEST",
     "instruments": ("EURHUF", "USDHUF"), "window_minutes": 30,
     "why": "the domestic funding benchmark -- and the one that DID NOT track the effective "
            "policy rate during the two-rate regime, which is the trap HU-B is built on"},
    {"name": "MNB one-day deposit quick tender (egynapos betéti gyorstender)",
     "local": "announced and allotted intraday, outside the monthly meeting calendar",
     "time_utc": "13:00", "time_utc_dst": "12:00", "dst_rule": "CET/CEST",
     "instruments": ("EURHUF", "USDHUF", "CHFHUF"), "window_minutes": 60,
     "why": "the EFFECTIVE policy instrument from 2022-10-14 to 2023-09-26; a daily decision "
            "that a monthly event calendar cannot see"},
    {"name": "MNB EUR/HUF FX swap tender",
     "local": "announced on the MNB's own schedule, intraday",
     "time_utc": "13:00", "time_utc_dst": "12:00", "dst_rule": "CET/CEST",
     "instruments": ("EURHUF", "USDHUF"), "window_minutes": 60,
     "why": "the instrument the MNB uses to move forint liquidity and the forward points "
            "without touching the spot rate; the swap point is the observable"},
    {"name": "Budapest Stock Exchange closing auction (the BUX close)",
     "local": "17:00-17:05 Europe/Budapest", "time_utc": "16:00", "time_utc_dst": "15:00",
     "dst_rule": "CET/CEST", "instruments": ("EUSTX50", "GER40"), "window_minutes": 15,
     "why": "the domestic close; no BUX CFD exists, so the European tape carries it"},
    {"name": "LBMA gold price PM auction (the MNB gold programme's reference)",
     "local": "15:00 Europe/London", "time_utc": "15:00", "time_utc_dst": "14:00",
     "dst_rule": "GMT/BST", "instruments": ("XAUUSD",), "window_minutes": 15,
     "why": "the MNB took its gold reserve from about three tonnes to more than a hundred in "
            "three announced steps; the purchases are disclosed and the reference is this"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "AKK government bond auction", "kind": "weekday", "weekday": 3, "roll": "next",
     "window_utc": ("09:00", "12:00"), "instruments": ("EURHUF", "USDHUF"),
     "why": "the debt agency auctions bonds on a published calendar, most often on Thursdays, "
            "with the results the same morning; the non-resident bid is the foreign flow"},
    {"name": "AKK discount treasury bill auction", "kind": "weekday", "weekday": 1,
     "roll": "next", "window_utc": ("09:00", "12:00"), "instruments": ("EURHUF",),
     "why": "the short end is auctioned on its own weekly clock, typically Tuesdays, which is "
            "also the rate-decision weekday -- a collision the pack separates rather than pools"},
    {"name": "MNB monthly reserve and balance-sheet publication", "kind": "month_end",
     "roll": "previous", "window_utc": ("08:00", "12:00"), "instruments": ("EURHUF", "XAUUSD"),
     "why": "the reserve series carries the conversion drawdown, the gold steps and the swap "
            "book; it is published a few business days after the month end"},
    {"name": "Month-end exporter and EU-transfer conversion", "kind": "month_end",
     "roll": "previous", "window_utc": ("07:00", "14:00"),
     "instruments": ("EURHUF", "EURPLN", "GER40"),
     "why": "Hungarian exporters invoice in EUR and the state converts EU receipts into HUF; "
            "both cluster into the month boundary"},
    {"name": "Quarter-end EU cohesion and RRF disbursement conversion", "kind": "quarter_end",
     "roll": "previous", "window_utc": ("08:00", "14:00"), "instruments": ("EURHUF", "EURPLN"),
     "why": "a forced EUR-to-HUF conversion whose SCHEDULE is political: suspended by a Council "
            "decision and released against legislative milestones"},
    {"name": "Fiscal year end (31 December) and the central budget act",
     "kind": "fiscal_year_end", "roll": "previous", "window_utc": ("08:00", "16:00"),
     "instruments": ("EURHUF", "XNGUSD"),
     "why": "the budget year is the calendar year; the utility price cap, the sectoral taxes "
            "and the funding plan are all dated to it"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Budapesti Ertektozsde (BET) -- BUX, BUMIX, CETOP",
     "index_symbols": (),
     "open_local": "09:00 (pre-open from 08:30)", "close_local": "17:05",
     "open_utc": "08:00", "close_utc": "16:05",
     "dst_rule": "CET/CEST on the EU rule",
     "auction": "opening call, continuous trading, closing call 17:00-17:05",
     "expiry_rule": "BUX futures exist on BET but are thinly traded; there is no deep monthly "
                    "index expiry clock to mine and the pack says so rather than inventing one",
     "holidays": "the statutory Hungarian calendar PLUS the decreed rest days, which are not "
                 "statutory holidays at all and are declared each year",
     "notes": "NO CFD IS QUOTED on the BUX and the index is four names; the two-lane order "
              "forbids hunting them, so this is a transmission target only"},
    {"name": "HUDEX and CEEGEX -- the Hungarian energy exchanges",
     "index_symbols": (), "open_local": "09:00", "close_local": "17:00",
     "open_utc": "08:00", "close_utc": "16:00", "dst_rule": "CET/CEST",
     "auction": "the day-ahead power auction clears coupled with the neighbouring zones; the "
                "gas spot clears on CEEGEX",
     "expiry_rule": "monthly, quarterly and yearly power and gas futures",
     "holidays": "the energy market runs every calendar day; a decreed rest day is a DEMAND "
                 "state and not a closure",
     "notes": "neither power nor Hungarian gas is quoted by this broker; the executable legs are "
              "the international gas benchmark and the crude benchmark"},
    {"name": "The interbank HUF market and the MNB's tenders",
     "index_symbols": (), "open_local": "08:00", "close_local": "17:00",
     "open_utc": "07:00", "close_utc": "16:00", "dst_rule": "CET/CEST",
     "auction": "the MNB's deposit, swap and discount-bond tenders, announced on its own "
                "schedule rather than on the meeting calendar",
     "expiry_rule": "OTC forwards and swaps; the swap points are the observable",
     "holidays": "the Hungarian banking calendar including the decreed rest days",
     "notes": "deep enough that SIX crosses are quoted at this broker, which is the structural "
              "advantage of this pack over every other CEE pack on the desk"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "hu_mnb_decision_cet", "start_utc": "12:30", "end_utc": "15:00",
     "notes": "the early-afternoon rate decision and the press conference, winter clock"},
    {"name": "hu_mnb_decision_cest", "start_utc": "11:30", "end_utc": "14:00",
     "notes": "the same local minutes on the summer clock; the two are never pooled"},
    {"name": "hu_fixing", "start_utc": "09:45", "end_utc": "10:30",
     "notes": "the 11:00 local official rate fix, winter clock"},
    {"name": "hu_ksh_release", "start_utc": "07:30", "end_utc": "08:30",
     "notes": "the 08:30 local KSH prints -- CPI, industrial production, trade, GDP -- which is "
              "half an hour before the German 08:00 CET releases and therefore READABLE "
              "SEPARATELY, unlike most CEE prints"},
    {"name": "hu_bet_session_cet", "start_utc": "08:00", "end_utc": "16:05",
     "notes": "the Budapest continuous session and closing call, winter clock"},
    {"name": "hu_auction_morning", "start_utc": "09:00", "end_utc": "12:00",
     "notes": "the AKK auction window; bonds most often Thursday, bills most often Tuesday"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "MNB rate decision (kamatdontes) and the Monetary Council statement",
     "cadence": "monthly", "time_utc": "13:00", "source": "Magyar Nemzeti Bank",
     "actual_series": "MNB:alapkamat", "expected_series": "MNB:egynapos_betet",
     "notes": "the last Tuesday of the month; THE CALENDAR IS NOT COMPLETE -- the one-day "
              "deposit tender was decided daily outside it from 2022-10-14 to 2023-09-26"},
    {"name": "MNB minutes (jegyzokonyv) of the Monetary Council", "cadence": "monthly",
     "time_utc": "13:00", "source": "Magyar Nemzeti Bank", "actual_series": "MNB:minutes",
     "expected_series": "UNMEASURED",
     "notes": "published about two weeks after the meeting; the vote is described rather than "
              "published as a named split"},
    {"name": "MNB official exchange rates (hivatalos devizaárfolyam)", "cadence": "daily",
     "time_utc": "10:00", "source": "Magyar Nemzeti Bank", "actual_series": "MNB:arfolyam_EURHUF",
     "expected_series": "n/a",
     "notes": "fixed at 11:00 local every working day; the machine-readable series library goes "
              "back decades"},
    {"name": "KSH consumer price index (fogyasztoiar-index)", "cadence": "monthly",
     "time_utc": "07:30", "source": "Kozponti Statisztikai Hivatal", "actual_series": "KSH:CPI",
     "expected_series": "UNMEASURED",
     "notes": "08:30 local, early in the month for the prior month; the regulated-energy line "
              "carries the utility price cap and is the HU-G object"},
    {"name": "KSH industrial production and external trade", "cadence": "monthly",
     "time_utc": "07:30", "source": "Kozponti Statisztikai Hivatal",
     "actual_series": "KSH:industrial_production", "expected_series": "UNMEASURED",
     "notes": "a first estimate and then a detailed release; the vehicles and battery lines are "
              "the German chain arriving as a Hungarian number"},
    {"name": "KSH GDP flash estimate", "cadence": "quarterly", "time_utc": "07:30",
     "source": "Kozponti Statisztikai Hivatal", "actual_series": "KSH:GDP_flash",
     "expected_series": "UNMEASURED",
     "notes": "about 30 days after the quarter, with a second estimate at 60 days"},
    {"name": "MNB foreign exchange reserves and gold (devizatartalek)", "cadence": "monthly",
     "time_utc": "08:00", "source": "Magyar Nemzeti Bank", "actual_series": "MNB:reserves",
     "expected_series": "n/a",
     "notes": "the 2014-2015 conversion drawdown and the gold accumulation steps are both "
              "visible in this one series"},
    {"name": "AKK auction results (allampapir aukcio)", "cadence": "weekly",
     "time_utc": "10:30", "source": "Allamadossag Kezelo Kozpont",
     "actual_series": "AKK:auction_yield", "expected_series": "UNMEASURED",
     "notes": "bonds most often Thursday and bills most often Tuesday, on a published quarterly "
              "calendar; the retail MAP Plusz programme runs continuously beside it"},
    {"name": "European Commission and Council decisions on Hungarian EU funds",
     "cadence": "irregular", "time_utc": "UNMEASURED", "source": "European Commission / Council",
     "actual_series": "EC:hu_funds_decision", "expected_series": "n/a",
     "notes": "the conditionality trigger, the suspension and the releases are DATED published "
              "decisions with a forced conversion behind each one"},
    {"name": "MEKH and government decrees on the utility price cap (rezsicsokkentes)",
     "cadence": "irregular", "time_utc": "UNMEASURED",
     "source": "Magyar Kozlony / MEKH", "actual_series": "MEKH:capped_tariff",
     "expected_series": "n/a",
     "notes": "an administered household energy price since 2013, narrowed on 2022-08-01 so "
              "that consumption above an average threshold pays the market price -- a dated "
              "step inside the CPI"},
)

# --------------------------------------------------------------------------- holidays
#: THE LABOUR CODE IS THE RULE (2012. evi I. torveny, Munka Torvenykonyve, 102. §). Eight fixed
#: solar days and three derived from Easter. Hungary does NOT substitute a holiday that falls at
#: the weekend -- but it DOES rearrange working days around one, which is a different and much
#: more troublesome mechanism (see SWAPPED_DAYS).
FIXED_NATIONAL: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Ujev"),
    (3, 15, "Nemzeti unnep -- az 1848-as forradalom"),
    (5, 1, "A munka unnepe"),
    (8, 20, "Az allamalapitas unnepe -- Szent Istvan"),
    (10, 23, "Nemzeti unnep -- az 1956-os forradalom"),
    (11, 1, "Mindenszentek"),
    (12, 25, "Karacsony"),
    (12, 26, "Karacsony masnapja"),
)
#: Good Friday (Nagypentek) became a public holiday only FROM 2017 -- a closed day that did not
#: exist before then, and a regime break a study pooling 2010-2026 will silently mislabel.
GOOD_FRIDAY_FROM = 2017
#: The Easter-derived closed days, as (offset from Easter Sunday in days, name, first year).
#: Pentecost Monday is Easter plus FIFTY days, which is why it must be computed and not typed.
EASTER_OFFSETS: tuple[tuple[int, str, int], ...] = (
    (-2, "Nagypentek", GOOD_FRIDAY_FROM),
    (1, "Husvethetfo", 1900),
    (50, "Punkosdhetfo", 1900),
)
#: NO WEEKEND SUBSTITUTION in the Labour Code: a holiday on a Saturday or Sunday is lost.
WEEKEND_SUBSTITUTION = False
#: THE THING NO RULE COMPUTES. Hungary REARRANGES the working calendar around public holidays by
#: ministerial decree: a Monday or Friday next to a holiday becomes a rest day, and a nearby
#: SATURDAY becomes a working day to pay for it. The decree is issued in the preceding year, so
#: the table below is DECLARED and dated and carries its own status -- a computed rule here
#: would be a fabrication (L1.28a).
#:   {year: ((rest day, the Saturday worked in its place, status), ...)}
SWAPPED_DAYS: dict[int, tuple[tuple[date, date, str], ...]] = {
    2024: ((date(2024, 8, 19), date(2024, 8, 3), "DECREE_DECLARED"),
           (date(2024, 12, 24), date(2024, 12, 7), "DECREE_DECLARED")),
    2025: ((date(2025, 5, 2), date(2025, 5, 17), "DECREE_DECLARED"),
           (date(2025, 10, 24), date(2025, 10, 18), "DECREE_DECLARED"),
           (date(2025, 12, 24), date(2025, 12, 13), "DECREE_DECLARED")),
    2026: (),
}
#: Why 2026 is empty rather than guessed.
SWAPPED_DAYS_STATUS: dict[int, str] = {
    2024: "DECREE_DECLARED and PRESS_REPORTED here; cite the ministerial decree in Magyar "
          "Kozlony before compiling a cell on either date",
    2025: "DECREE_DECLARED and PRESS_REPORTED here; cite the decree before use",
    2026: "NOT_DECLARED IN THIS PACK. The work-schedule decree for a year is published in the "
          "preceding year and this pack refuses to invent it; a 2026 bridge-day cell is "
          "UNMEASURED until the decree is read",
}


def easter_sunday(year: int) -> date:
    """Easter Sunday by the ANONYMOUS GREGORIAN ALGORITHM -- computed, never typed.

    All three Hungarian movable holidays hang off this one date, and Pentecost Monday is fifty
    days after it, so a typed table would be three chances a year to be wrong.
    """
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month = (h + ell - 7 * m + 114) // 31
    day = ((h + ell - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def easter_holidays(year: int) -> dict[date, str]:
    """The Easter-derived Hungarian closed days, respecting the year each became one."""
    base = easter_sunday(year)
    return {base + timedelta(days=off): name
            for off, name, since in EASTER_OFFSETS if year >= since}


def national_holidays(year: int) -> dict[date, str]:
    """The STATUTORY Hungarian closed days: eight fixed dates plus the three Easter-derived.

    DERIVED FROM THE RULE, not typed. The decreed rest days are NOT here -- they are not
    statutory holidays and they live in `SWAPPED_DAYS`, which is declared and dated.
    """
    out: dict[date, str] = {}
    for m, d, name in FIXED_NATIONAL:
        out[date(year, m, d)] = name
    out.update(easter_holidays(year))
    return dict(sorted(out.items()))


def bridge_rest_days(year: int) -> dict[date, str]:
    """The DECREED rest days for a year: not statutory holidays, but days on which the country
    and its exchange are shut. Empty when the decree has not been read into this pack."""
    return {rest: f"athelyezett pihenonap (worked on {worked.isoformat()}) [{status}]"
            for rest, worked, status in SWAPPED_DAYS.get(year, ())}


def working_saturdays(year: int) -> dict[date, str]:
    """The Saturdays that were turned into WORKING days to pay for a bridge rest day.

    THE REASON THIS IS PUBLISHED. A Hungarian working Saturday is a real domestic session with
    no European counterpart at all: the local corporates, the banks' back offices and the
    administration are at work while every neighbouring market is closed. A liquidity study
    that treats every Saturday as identical misses the only ones that are not.
    """
    return {worked: f"munkanap (for the rest day on {rest.isoformat()}) [{status}]"
            for rest, worked, status in SWAPPED_DAYS.get(year, ())}


def rest_days(year: int) -> dict[date, str]:
    """Every day the country is shut: the statutory calendar plus the decreed rest days."""
    out = dict(national_holidays(year))
    out.update(bridge_rest_days(year))
    return dict(sorted(out.items()))


def bank_holidays(year: int) -> dict[date, str]:
    return rest_days(year)


def market_holidays(year: int) -> dict[date, str]:
    """BET closed days: the rest-day calendar on WEEKDAYS only, because a Saturday closure costs
    no session and must never enter a holiday-liquidity sample as one."""
    return {d: n for d, n in rest_days(year).items() if d.weekday() < 5}


def lost_weekend_holidays(year: int) -> dict[date, str]:
    """The statutory days that fall at the weekend and are therefore LOST: the Labour Code
    grants no substitute. This is the half of the calendar a naive closed-day count invents."""
    return {d: n for d, n in national_holidays(year).items() if d.weekday() >= 5}


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


def _last_sunday(year: int, month: int) -> date:
    day = date(year, month, 31)
    return day - timedelta(days=(day.weekday() + 1) % 7)


def dst_start(year: int) -> date:
    """The last Sunday of March: CEST begins."""
    return _last_sunday(year, 3)


def dst_end(year: int) -> date:
    """The last Sunday of October: CET returns."""
    return _last_sunday(year, 10)


def utc_offset_hours(day: date) -> int:
    """Europe/Budapest's UTC offset on a date: 1 in CET, 2 in CEST, computed from the EU rule."""
    return 2 if dst_start(day.year) <= day < dst_end(day.year) else 1


def release_minute_utc(day: date, local_hhmm: str = "08:30") -> str:
    """The UTC minute a fixed LOCAL Hungarian release time lands on for a given date.

    THE POINT OF THIS FUNCTION. KSH prints at 08:30 local and the German releases land at 08:00
    CET, so on the winter clock the Hungarian print is READABLE SEPARATELY at 07:30 UTC, half an
    hour after the German one -- and on the summer clock both move together. A UTC window
    written once and pooled across a year silently merges two different orderings.
    """
    hh, _, mm = local_hhmm.partition(":")
    return f"{int(hh) - utc_offset_hours(day):02d}:{mm}"


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_statute_plus_declared_decree",
    "authority": "2012. evi I. torveny (Munka Torvenykonyve) 102. § for the statutory holidays; "
                 "an annual ministerial decree in Magyar Kozlony for the work-schedule swaps",
    "rule": "EIGHT FIXED SOLAR DAYS -- 1 Jan (Ujev), 15 Mar (1848), 1 May (a munka unnepe), "
            "20 Aug (Szent Istvan), 23 Oct (1956), 1 Nov (Mindenszentek), 25 Dec and 26 Dec -- "
            "PLUS THREE EASTER-DERIVED DAYS computed with the anonymous Gregorian algorithm: "
            "Nagypentek (Easter minus 2, a public holiday only FROM 2017), Husvethetfo (Easter "
            "plus 1) and Punkosdhetfo (Easter plus FIFTY). NO WEEKEND SUBSTITUTION: a holiday "
            "at the weekend is lost. BUT THE WORKING CALENDAR IS REARRANGED BY DECREE: a Monday "
            "or Friday beside a holiday is made a rest day and a nearby SATURDAY is made a "
            "working day to pay for it. Those swaps follow NO rule -- they are declared each "
            "year in SWAPPED_DAYS with their status, and 2026 is deliberately empty because the "
            "decree has not been read (L1.28a). THE CLOCK ALSO MOVES: Europe/Budapest is CET in "
            "winter and CEST in summer on the EU rule.",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "national_rule": "see `rule`; `national_holidays(year)` is the computed statutory form",
    "market_rule": "the rest-day calendar (statutory plus decreed) on weekdays; BET keeps its "
                   "local hours all year and therefore moves an hour in UTC at each DST "
                   "boundary",
    "easter_rule": "anonymous Gregorian algorithm in `easter_sunday(year)`; Nagypentek counts "
                   "only from 2017 and Punkosdhetfo is Easter plus fifty days",
    "substitution_rule": "NONE for a weekend holiday -- `lost_weekend_holidays` is published as "
                         "its own series; the SWAP mechanism is a different thing entirely and "
                         "is carried in SWAPPED_DAYS with `working_saturdays` beside it",
    "swap_rule": "DECLARED, NOT COMPUTED. The annual work-schedule decree is the only authority "
                 "and a year with no decree in this pack produces no bridge days at all",
    "dst_rule": "EU rule: CEST from the last Sunday of March to the last Sunday of October; "
                "`utc_offset_hours` and `release_minute_utc` compute it",
    "table": {y: {d.isoformat(): n for d, n in rest_days(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {2024: "COMPUTED statutory days (Easter Sunday 2024-03-31, so Nagypentek "
                     "2024-03-29, Husvethetfo 2024-04-01, Punkosdhetfo 2024-05-20) PLUS two "
                     "DECREE_DECLARED bridge rest days",
               2025: "COMPUTED statutory days (Easter Sunday 2025-04-20, so Nagypentek "
                     "2025-04-18, Husvethetfo 2025-04-21, Punkosdhetfo 2025-06-09) PLUS three "
                     "DECREE_DECLARED bridge rest days",
               2026: "COMPUTED statutory days only (Easter Sunday 2026-04-05, so Nagypentek "
                     "2026-04-03, Husvethetfo 2026-04-06, Punkosdhetfo 2026-05-25); the work-"
                     "schedule decree is NOT_DECLARED in this pack and no bridge day is "
                     "invented for it"},
    "known_dates": {
        "2024-05-20": "Punkosdhetfo, computed as Easter 2024-03-31 plus fifty days",
        "2025-06-09": "Punkosdhetfo, computed as Easter 2025-04-20 plus fifty days",
        "2025-12-24": "a DECREED rest day, not a statutory holiday; 2025-12-13 was worked",
        "2026-10-23": "Nemzeti unnep, a fixed solar date certain in any year",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "bank_fn": bank_holidays,
    "easter_fn": easter_sunday,
    "lost_fn": lost_weekend_holidays,
    "bridge_fn": bridge_rest_days,
    "working_saturday_fn": working_saturdays,
    "utc_offset_fn": utc_offset_hours,
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "AKK holder structure of Hungarian government securities",
     "root": "https://www.akk.hu/statisztika",
     "fields": ("non_resident_share_pct", "household_share_pct", "by_holder_type",
                "outstanding_huf"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "10:00", "lag_days": 25,
     "licence": "free, public", "available": True,
     "why": "the only published measure of foreign positioning in forint assets, AND the only "
            "published measure of the household retail-bond programme that competes with it; "
            "the two lines move against each other and that is the HU-J object",
     "pit_warning": "a month stale; it conditions a quarter, never a week"},
    {"name": "MNB foreign exchange reserves, gold and the swap book",
     "root": "https://www.mnb.hu/statisztika/statisztikai-adatok-informaciok/adatok-idosorok",
     "fields": ("reserves_eur", "gold_tonnes", "fx_swap_outstanding", "imf_reserve_position"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "08:00", "lag_days": 5,
     "licence": "free, public", "available": True,
     "why": "the 2014-2015 conversion drawdown, the gold accumulation steps and the size of the "
            "swap book are all in this one series",
     "pit_warning": "prompt but monthly; the swap book's TENOR mix is not published at all"},
    {"name": "MNB balance-sheet detail: the one-day and one-week deposit stock",
     "root": "https://www.mnb.hu/statisztika",
     "fields": ("overnight_deposit_stock", "one_week_deposit_stock", "discount_bond_stock"),
     "frequency": "weekly", "snapshot": "tender day", "publish_utc": "13:00", "lag_days": 3,
     "licence": "free, public", "available": True,
     "why": "the SIZE of the two-rate regime: how much money was actually parked at 18% is the "
            "difference between a headline rate and a binding one",
     "pit_warning": "the stock is published with a short lag; the tender ALLOTMENT is same-day "
                    "and is the faster observable"},
    {"name": "BET turnover statistics and the foreign share",
     "root": "https://www.bet.hu/oldalak/statisztika",
     "fields": ("foreign_turnover_share", "by_member", "by_instrument"),
     "frequency": "monthly", "snapshot": "calendar month", "publish_utc": "12:00",
     "lag_days": 15, "licence": "free, public", "available": True,
     "why": "the equity-side foreign flow; concentrated in four names, which BOUNDS what HU-L "
            "can ever claim rather than licensing a claim",
     "pit_warning": "turnover share is not ownership"},
    {"name": "a CFTC or exchange-traded forint positioning series",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: no forint future trades on any exchange the desk reads and no COT "
            "contract exists for HUF",
     "pit_warning": "DOES NOT EXIST: forint positioning is UNMEASURED and is never proxied by "
                    "the EUR COT leg. THE SIX-CROSS PANEL IS THE SUBSTITUTE the pack actually "
                    "uses: a common factor across EURHUF, USDHUF, AUDHUF, CHFHUF, GBPHUF and "
                    "NZDHUF is a forint move, and a cross-specific residual is not"},
)

# --------------------------------------------------------------------------- terminology
#: HUNGARIAN IS A LATIN SCRIPT WITH TWO LETTERS ALMOST NOTHING ELSE HAS -- ő and ű. That is what
#: makes this failure invisible: a crawler handed de-accented terms searches "kamatdontes" and
#: never finds "kamatdöntés", and a crawler handed English reads the wire summary of an MNB
#: decision and never the decision. Every group below carries the Hungarian term with its
#: accents, and the tests assert it.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "HU-A": ("Magyar Nemzeti Bank", "Monetáris Tanács", "kamatdöntés", "alapkamat",
             "inflációs cél", "Inflációs jelentés", "kamatfolyosó", "jegybanki alapkamat",
             "monetáris politika", "sajtótájékoztató", "jegyzőkönyv",
             "kamatdöntő ülés", "jegybanki előrejelzés"),
    "HU-B": ("egynapos betéti gyorstender", "egynapos betét", "effektív kamat",
             "kéthetes betét", "egyhetes betét", "irányadó eszköz", "kamatkonvergencia",
             "diszkont jegybanki kötvény", "kamatemelés", "kamatcsökkentés",
             "kötelező tartalékráta", "effektív kamatszint"),
    "HU-C": ("devizaswap tender", "FX swap eszköz", "forintlikviditás", "swappont",
             "jegybanki tender", "devizatartalék", "forintlikviditást nyújtó eszköz",
             "tőkeáramlás", "bankközi piac működése"),
    "HU-D": ("forint árfolyam", "euró forint keresztárfolyam", "svájci frank árfolyam",
             "forintgyengülés", "forinterősödés", "árfolyamsáv", "carry ügylet",
             "kamatkülönbözet", "hivatalos devizaárfolyam",
             "külföldi befektető", "befektetői pozíciók"),
    "HU-E": ("helyreállítási alap", "uniós források", "jogállamisági eljárás",
             "feltételességi mechanizmus", "kifizetési kérelem", "mérföldkövek",
             "kohéziós források", "felfüggesztett források", "Európai Bizottság döntése",
             "költségvetési előirányzat"),
    "HU-F": ("devizahitel", "forintosítás", "végtörlesztés", "elszámolási törvény",
             "svájci frank alapú jelzáloghitel", "árfolyamgát", "lakossági devizahitel",
             "hitelfelvevő", "törlesztőrészlet"),
    "HU-G": ("rezsicsökkentés", "hatósági ár", "árstop", "átlagfogyasztás feletti ár",
             "lakossági energiaár", "MEKH határozat", "fogyasztóiár-index",
             "maginfláció", "élelmiszerárstop", "fűtési szezon",
             "egyetemes szolgáltató"),
    "HU-H": ("Barátság kőolajvezeték", "kőolajimport", "szankciós mentesség",
             "finomítói árrés", "orosz kőolaj", "különadó", "üzemanyagár",
             "energiaimport-függőség", "kőolajfinomító",
             "üzemanyagtöltő állomás"),
    "HU-I": ("Paks II", "atomerőmű bővítés", "orosz hitel", "energiamix",
             "földgázimport", "gáztározó", "hosszú távú gázszerződés", "villamosenergia-import"),
    "HU-J": ("államkötvény aukció", "Államadósság Kezelő Központ", "diszkont kincstárjegy",
             "aukciós hozam", "lakossági állampapír", "Magyar Állampapír Plusz",
             "államadósság", "nem rezidens tulajdonosi arány",
             "elsődleges forgalmazó"),
    "HU-K": ("Központi Statisztikai Hivatal", "fogyasztóiár-index", "ipari termelés",
             "külkereskedelmi mérleg", "bruttó hazai termék", "első becslés",
             "munkanélküliségi ráta", "kiskereskedelmi forgalom", "keresetek alakulása",
             "előzetes adatok", "beruházások bővülése"),
    "HU-L": ("Budapesti Értéktőzsde", "BUX index", "tőzsdei forgalom", "elszámolás",
             "munkaszüneti nap", "áthelyezett pihenőnap", "munkanap áthelyezés",
             "nemzeti ünnep", "Nagypéntek", "Pünkösdhétfő", "nyári időszámítás",
             "tőzsdei kereskedési nap"),
    "HU-M": ("aranytartalék", "aranyvásárlás", "tartalékkezelés", "jegybanki mérleg",
             "tartalékok összetétele", "tonna arany", "tartalékbővítés",
             "aranyvásárlási program időzítése"),
}

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

#: The letters that make a string HUNGARIAN rather than de-accented mush.
_HUNGARIAN_CHARS = "áéíóöőúüűÁÉÍÓÖŐÚÜŰ"
#: The two letters that are Hungarian and essentially nothing else: ő and ű. A string with only
#: á/é/í could be Spanish or Czech; one with ő is Hungarian.
_HUNGARIAN_UNIQUE_CHARS = "őűŐŰ"


def has_hungarian(text: str) -> bool:
    """True when the text carries at least one Hungarian accented vowel."""
    return any(ch in _HUNGARIAN_CHARS for ch in str(text))


def has_hungarian_unique(text: str) -> bool:
    """True when the text carries ő or ű -- letters that are Hungarian and almost nothing else."""
    return any(ch in _HUNGARIAN_UNIQUE_CHARS for ch in str(text))


def hungarian_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return [t for terms in rows.values() for t in terms if has_hungarian(t)]


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
        "hu_mnb", "Magyar Nemzeti Bank: rate decisions and Council statements, the minutes, the "
                  "Inflation Report, the official exchange rates, the tenders and the full "
                  "statistical time-series library", layer="official",
        roots=("https://www.mnb.hu/monetaris-politika/a-monetaris-tanacs/kozlemenyek",
               "https://www.mnb.hu/kiadvanyok/jelentesek/inflacios-jelentes",
               "https://www.mnb.hu/statisztika/statisztikai-adatok-informaciok/adatok-idosorok",
               "https://www.mnb.hu/monetaris-politika/eszkoztar"),
        queries=("Monetáris Tanács közleménye", "kamatdöntés bejelentés", "alapkamat változás",
                 "egynapos betéti gyorstender", "hivatalos devizaárfolyam",
                 "Inflációs jelentés", "devizatartalék alakulása", "jegybanki eszköztár"),
        languages=("hu", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (mnb.hu terms)",
        notes="the one root that carries BOTH policy rates: the monthly base-rate decision and "
              "the daily one-day deposit tender that was the effective rate for eleven months. "
              "A crawl that reads only the Monetary Council page misses the instrument that "
              "actually bound"),
    source_class(
        "hu_ksh", "Központi Statisztikai Hivatal: CPI, industrial production, external trade, "
                  "GDP, wages and the STADAT open database", layer="official",
        roots=("https://www.ksh.hu/gyorstajekoztatok", "https://www.ksh.hu/stadat",
               "https://www.ksh.hu/s/kiadvanyok/"),
        queries=("fogyasztóiár-index gyorstájékoztató", "maginfláció", "ipari termelés volumene",
                 "külkereskedelmi termékforgalom", "bruttó hazai termék első becslés",
                 "STADAT táblák", "havi keresetek"),
        languages=("hu", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the 08:30 LOCAL print is half an hour ahead of the 08:00 CET German releases on "
              "the winter clock, so the Hungarian number is readable on its own -- a rare "
              "ordering advantage this pack keeps in `release_minute_utc`"),
    source_class(
        "hu_akk", "Államadósság Kezelő Központ: the issuance calendar, auction results, the "
                  "holder structure and the retail government securities programme",
        layer="official",
        roots=("https://www.akk.hu/aukciok", "https://www.akk.hu/statisztika",
               "https://www.allampapir.hu"),
        queries=("államkötvény aukció eredmény", "diszkont kincstárjegy aukció",
                 "aukciós naptár", "nem rezidens tulajdonosi arány",
                 "Magyar Állampapír Plusz hozam", "lakossági állampapír értékesítés"),
        languages=("hu", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the RETAIL programme is unusually large here and competes with the wholesale "
              "curve and with bank deposits at once; the two holder lines move against each "
              "other and that opposition is the HU-J object"),
    source_class(
        "hu_kozlony", "Magyar Közlöny and the Nemzeti Jogszabálytár: the gazette where every "
                      "price cap, sectoral tax, work-schedule decree and energy measure becomes "
                      "citable", layer="official",
        roots=("https://magyarkozlony.hu", "https://njt.hu"),
        queries=("Magyar Közlöny kormányrendelet", "munkaszüneti napok körüli munkarend",
                 "hatósági ár rendelet", "különadó rendelet", "árstop meghosszabbítás",
                 "veszélyhelyzeti kormányrendelet"),
        languages=("hu",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (official gazette)",
        notes="THE WORK-SCHEDULE DECREE LIVES HERE, and it is the only authority for the bridge "
              "rest days and working Saturdays that no rule computes; so does every price cap "
              "and sectoral tax, many of them issued as emergency decrees"),
    source_class(
        "hu_mekh_energy", "Magyar Energetikai és Közmű-szabályozási Hivatal and the Ministry of "
                          "Energy: tariff decisions, the utility price cap, storage levels and "
                          "the security-of-supply reports", layer="official",
        roots=("https://www.mekh.hu/hatarozatok", "https://www.mekh.hu/kiadvanyok",
               "https://kormany.hu/energiaugyi-miniszterium"),
        queries=("MEKH határozat földgáz ár", "rezsicsökkentett ár", "átlagfogyasztás feletti "
                 "energiaár", "földgáztároló telítettség", "egyetemes szolgáltatás ára",
                 "ellátásbiztonsági jelentés"),
        languages=("hu",), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the 2022-08-01 narrowing of the household price cap -- market price above an "
              "average consumption threshold -- is a DATED administered step inside the CPI and "
              "the single largest Hungarian inflation event of the decade"),
    source_class(
        "hu_eu_institutions", "The European Commission and Council: the conditionality "
                              "mechanism, the suspension decisions, the RRF payment requests "
                              "and the milestone assessments", layer="official",
        roots=("https://commission.europa.eu/business-economy-euro/economic-recovery/"
               "recovery-and-resilience-facility_en",
               "https://www.consilium.europa.eu/en/press/press-releases/",
               "https://palyazat.gov.hu"),
        queries=("jogállamisági feltételességi mechanizmus", "uniós források felfüggesztése",
                 "helyreállítási terv mérföldkövek", "kifizetési kérelem Magyarország",
                 "kohéziós források felszabadítása", "Tanács döntése Magyarországról"),
        languages=("hu", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="THE DATES ARE THE EVENT. A Council suspension and a Commission release are "
              "published decisions on published days with a large forced conversion behind "
              "each; Czechia, which faced none of it, is the clean control"),
    # ---- institutional
    source_class(
        "hu_bet_keler", "Budapesti Értéktőzsde and KELER: the BUX composition, turnover and "
                        "foreign share, the trading calendar and the settlement rules",
        layer="institutional",
        roots=("https://www.bet.hu/oldalak/statisztika", "https://www.bet.hu/oldalak/indexek",
               "https://www.keler.hu"),
        queries=("BUX index összetétel", "tőzsdei forgalom statisztika", "tőzsdei naptár",
                 "elszámolási ciklus", "külföldi befektetők aránya", "osztalékfizetés naptár"),
        languages=("hu", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the exchange has been majority-owned by the CENTRAL BANK since 2015, which is an "
              "institutional fact with no parallel elsewhere on this desk; the trading calendar "
              "is also where the decreed rest days become a session fact"),
    source_class(
        "hu_bank_research", "Openly published Hungarian bank and broker research: Erste, OTP "
                            "Elemzési Központ, K&H, Raiffeisen, Equilor and Concorde",
        layer="institutional",
        roots=("https://www.otpbank.hu/portal/hu/Megtakaritas/Elemzesek",
               "https://www.erstemarket.hu", "https://www.equilor.hu/elemzesek/"),
        queries=("kamatdöntés várakozás", "forint árfolyam előrejelzés", "inflációs várakozás",
                 "elemzői konszenzus MNB", "heti piaci összefoglaló", "makrogazdasági "
                 "előrejelzés"),
        languages=("hu", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free notes; some behind registration",
        notes="the pre-meeting consensus these desks publish is the EXPECTATION an MNB surprise "
              "is measured against; during the two-rate regime they were among the few sources "
              "that quoted the EFFECTIVE rate rather than the base rate"),
    source_class(
        "hu_associations", "Industry and professional bodies: the Hungarian Banking "
                           "Association, MGYOSZ, the automotive suppliers' association and the "
                           "chamber of commerce", layer="institutional",
        roots=("https://www.bankszovetseg.hu", "https://mgyosz.hu", "https://mkik.hu"),
        queries=("Bankszövetség közlemény", "hitelezési folyamatok", "munkaerőhiány felmérés",
                 "vállalati energiaköltségek", "beszállítói ipar helyzete",
                 "különadó hatása a bankokra"),
        languages=("hu",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the Banking Association is the one body that publishes the sector's own view of "
              "the extra-profit taxes and the interest-rate caps, which are recurring Hungarian "
              "policy instruments with no equivalent in the Czech pack"),
    # ---- academic
    source_class(
        "hu_academic", "Corvinus, KRTK (HUN-REN Közgazdaság- és Regionális Tudományi "
                       "Kutatóközpont), the MNB's own working papers and the Hungarian "
                       "economic journals", layer="academic",
        roots=("https://www.mnb.hu/kiadvanyok/elemzesek-tanulmanyok-statisztikak/mnb-tanulmanyok",
               "https://kti.krtk.hu/publikaciok/", "https://www.uni-corvinus.hu/kutatas/",
               "https://openalex.org"),
        queries=("devizahitelezés következményei", "forintosítás hatása",
                 "monetáris transzmisszió Magyarországon", "árfolyam-begyűrűzés",
                 "kamatkonvergencia elemzés", "uniós források makrohatása"),
        languages=("hu", "en"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access / publisher terms",
        notes="the household FX-loan literature written in Budapest is the mechanism source for "
              "HU-F: it describes the balance-sheet loop the 2015 conversion cut, which is what "
              "makes CHFHUF before and after 2015 two different relationships"),
    source_class(
        "hu_energy_academic", "REKK (Regionális Energiagazdasági Kutatóközpont) and the energy "
                              "policy institutes: gas market models, storage economics, "
                              "interconnector studies and the Paks II analyses", layer="academic",
        roots=("https://rekk.hu/kutatas", "https://www.mekh.hu/kiadvanyok"),
        queries=("regionális gázpiaci modell", "gáztároló kapacitás elemzés",
                 "villamosenergia-import függőség", "Paks II gazdasági elemzés",
                 "ellátásbiztonsági kockázat", "orosz gázszállítás alternatívái"),
        languages=("hu", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access",
        notes="REKK is the one independent quantitative read on Hungarian gas and power, which "
              "is what makes HU-I a mechanism and not a headline"),
    # ---- practitioner
    source_class(
        "hu_portfolio_vg", "The Hungarian market desk press: Portfolio.hu, Világgazdaság (vg.hu), "
                           "Napi.hu and Privátbankár", layer="practitioner",
        roots=("https://www.portfolio.hu", "https://www.vg.hu", "https://www.napi.hu",
               "https://privatbankar.hu"),
        queries=("forint árfolyam ma", "kamatdöntés elemzés", "állampapír aukció eredménye",
                 "MNB kommunikáció értékelése", "uniós pénzek hatása a forintra",
                 "energiaárak alakulása", "tőzsdenyitás Budapesten"),
        languages=("hu",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="Portfolio.hu is the de facto national market tape and was the source that "
              "tracked the one-day deposit tender DAILY when the official calendar did not; "
              "its archive is the practical event log of the two-rate regime"),
    source_class(
        "hu_retail_finance_desk", "The retail savings and mortgage practitioners: Bankmonitor, "
                                  "Bankráció, Pénzcentrum and the state's own allampapir.hu "
                                  "calculators", layer="practitioner",
        roots=("https://bankmonitor.hu", "https://www.penzcentrum.hu",
               "https://www.allampapir.hu/kalkulator"),
        queries=("lakossági állampapír hozam kalkulátor", "banki betéti kamat összehasonlítás",
                 "hitelkamat változás", "megtakarítási forma választás",
                 "inflációkövető állampapír", "kamatplafon hatása"),
        languages=("hu",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="publisher terms",
        notes="the retail bond programme is so large here that the household's SAVINGS CHOICE "
              "is a macro variable; these sites publish the comparison the household actually "
              "makes, which dates the migration episodes HU-J is about"),
    # ---- retail ecology
    source_class(
        "hu_retail_forums", "Hungarian retail communities: r/hungary and r/koronavirus finance "
                            "threads, the Portfolio and Privátbankár comment sections, Facebook "
                            "investing groups and the Hungarian personal-finance blogs",
        layer="retail_ecology",
        roots=("https://www.reddit.com/r/hungary/", "https://www.facebook.com/groups/tozsdehu",
               "https://www.penzcentrum.hu/forum/"),
        queries=("hova tegyem a pénzem", "állampapír vagy betét", "euróban tartsam a "
                 "megtakarítást", "forintgyengülés mit jelent", "tőzsdei kezdő tanácsok",
                 "devizahiteles tapasztalatok"),
        languages=("hu",), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="KEPT AT LOW WEIGHT and never a source of edge: what it dates is the household "
              "CURRENCY-SUBSTITUTION episode -- the weeks when Hungarians moved forint savings "
              "into euro cash or into inflation-linked retail bonds, which is a real HU-D and "
              "HU-J observable and one the aggregates see months later"),
    source_class(
        "hu_retail_brokers", "Hungarian-language retail broker marketing, YouTube and Telegram "
                             "trading channels and the prop-firm affiliates",
        layer="retail_ecology",
        roots=("https://www.youtube.com/results?search_query=tőzsde+kezdőknek",
               "https://t.me/s/tozsdehu"),
        queries=("forex kereskedés magyarul", "tőkeáttétel kockázata", "ingyenes jelzések",
                 "prop cég kihívás", "demó számla", "arany kereskedés"),
        languages=("hu",), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="ESMA leverage caps apply (Hungary is an EU member state), so this is a REGULATED "
              "retail base; kept because the XAUUSD and GER40 stop clusters it advertises are a "
              "real microstructure observable"),
    # ---- app ecosystem
    source_class(
        "hu_official_apis", "The machine-readable official endpoints: the MNB exchange-rate web "
                            "service and time-series library, the KSH STADAT tables and the "
                            "Hungarian open-data portal", layer="app_ecosystem",
        roots=("https://www.mnb.hu/arfolyam-lekerdezes",
               "https://www.mnb.hu/statisztika/statisztikai-adatok-informaciok/adatok-idosorok",
               "https://www.ksh.hu/stadat", "https://data.gov.hu"),
        queries=("MNB árfolyam lekérdezés szolgáltatás", "statisztikai idősorok letöltése",
                 "STADAT táblák adatletöltés", "nyílt adatok Magyarország",
                 "gépi olvasható adat"),
        languages=("hu", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public open data",
        notes="the MNB publishes a long-running exchange-rate query service and a deep "
              "time-series library, so the HUF fixing history and the reserve series need no "
              "scraper -- which is what makes the six-cross panel cheap to maintain"),
    source_class(
        "hu_retail_apps", "The apps a Hungarian actually invests and pays through: the "
                          "Államkincstár WebKincstár and Magyar Állampapír app, Erste "
                          "MarketTrader, OTP eBROKER, Revolut and Wise, and the instant "
                          "payment system", layer="app_ecosystem",
        roots=("https://www.allamkincstar.gov.hu", "https://www.otpbank.hu/ebroker",
               "https://www.erstemarket.hu"),
        queries=("állampapír vásárlás online", "WebKincstár belépés", "értékpapírszámla díjak",
                 "azonnali fizetési rendszer", "devizaváltás alkalmazás",
                 "befektetési app összehasonlítás"),
        languages=("hu",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="app store and publisher terms",
        notes="the Treasury's own retail channel is the distribution system for the largest "
              "household bond programme in the region; its subscription totals are the fastest "
              "read on the savings migration"),
    # ---- media
    source_class(
        "hu_wire_press", "MTI (the state wire), hvg.hu, Telex, 24.hu, Index and the business "
                         "pages of the national dailies", layer="media",
        roots=("https://mti.hu", "https://hvg.hu/gazdasag", "https://telex.hu/gazdasag",
               "https://24.hu/fn/gazdasag/", "https://index.hu/gazdasag/"),
        queries=("MNB kamatdöntés bejelentés", "forint történelmi mélyponton",
                 "rezsicsökkentés módosítás", "uniós pénzek tárgyalás",
                 "kormányinfó gazdasági bejelentés", "különadó bejelentés"),
        languages=("hu",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="MTI carries the minute of a decree when the gazette carries only a date; hvg and "
              "Telex report the POLITICS of a price cap or an EU negotiation, which is the half "
              "of a Hungarian policy event a number-only crawl never sees"),
    source_class(
        "hu_licensed_assessments", "Licensed terminals and price reporting agencies: Bloomberg, "
                                   "LSEG/Refinitiv, and Argus / ICIS / Platts for Urals "
                                   "differentials, Central European gas and refining margins",
        layer="media",
        roots=("https://www.argusmedia.com", "https://www.icis.com"),
        queries=("Urals differential assessment", "CEGH gas price assessment",
                 "European refining margin", "Druzhba pipeline crude netback"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="subscription; terms forbid machine extraction",
        machine_use_allowed=False,
        notes="REGISTERED, NEVER SCRAPED: the Urals-to-Brent discount that IS the Hungarian "
              "refining advantage is a paywalled assessment, so HU-H is measured on the "
              "executable crude benchmark and on the disclosed refiner margin instead -- the "
              "absence is named rather than worked around"),
    # ---- archive
    source_class(
        "hu_mnb_ksh_archive", "The MNB statistical time-series library and the KSH yearbooks: "
                              "the long history of the policy rate, the forint, the reserves "
                              "and the national accounts, including discontinued series",
        layer="archive",
        roots=("https://www.mnb.hu/statisztika/statisztikai-adatok-informaciok/adatok-idosorok",
               "https://www.ksh.hu/evkonyvek", "https://www.ksh.hu/stadat"),
        queries=("történeti idősor jegybanki alapkamat", "forint árfolyam történeti adatok",
                 "statisztikai évkönyv", "megszűnt idősor", "módszertani változás",
                 "devizatartalék történeti alakulása"),
        languages=("hu", "en"), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the MNB library keeps the one-day and one-week deposit series alongside the base "
              "rate, which is the only way the two-rate regime can be reconstructed at all"),
    source_class(
        "hu_kozlony_library", "The Magyar Közlöny full run, the Nemzeti Jogszabálytár "
                              "consolidated texts, the Arcanum digital library and the "
                              "Parliament's records", layer="archive",
        roots=("https://magyarkozlony.hu/hivatalos-lapok", "https://njt.hu",
               "https://adt.arcanum.com", "https://www.parlament.hu/orszaggyulesi-naplo"),
        queries=("Magyar Közlöny archívum", "hatályos szöveg időállapot",
                 "Arcanum digitális tudománytár gazdaság", "országgyűlési napló költségvetés",
                 "korábbi rendelet szövege", "munkarend rendelet archívum"),
        languages=("hu",), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED",
        licence="free gazette; Arcanum is subscription for the full archive",
        notes="the consolidated law database keeps TIME-STAMPED versions, so what a price cap "
              "said on a given day is recoverable exactly -- which is what turns HU-G from a "
              "story into a dated administered-price series"),
    source_class(
        "hu_wayback", "web.archive.org snapshots of the MEKH tariff pages, the AKK auction "
                      "calendar and the allampapir.hu rate pages, all of which overwrite in "
                      "place", layer="archive",
        roots=("https://web.archive.org/web/*/mekh.hu*",
               "https://web.archive.org/web/*/akk.hu*",
               "https://web.archive.org/web/*/allampapir.hu*"),
        queries=("MEKH ár archívum", "AKK aukciós naptár archívum",
                 "állampapír kamat archívum"),
        languages=("hu", "en"), access_label="PUBLIC_ARCHIVE", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="Internet Archive terms",
        notes="the retail bond rate page and the tariff pages show TODAY's number and keep no "
              "vintage, so the point-in-time history of the household savings choice exists "
              "only in a crawl somebody took"),
    # ---- physical economy
    source_class(
        "hu_gas_power", "FGSZ (the gas transmission system operator), MAVIR (the electricity "
                        "TSO), the Hungarian Gas Storage operator and the ENTSOG/ENTSO-E "
                        "transparency platforms", layer="physical_economy",
        roots=("https://fgsz.hu/informacios-platform", "https://www.mavir.hu/web/mavir/adatok",
               "https://transparency.entsog.eu", "https://transparency.entsoe.eu"),
        queries=("földgáz betáplálás adatok", "gáztároló telítettség napi adat",
                 "villamosenergia-rendszer terhelése", "határkeresztező kapacitás",
                 "importszaldó villamos energia", "szállítási kapacitás aukció"),
        languages=("hu", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (registration for some feeds)",
        notes="Hungary is a LANDLOCKED gas importer with large storage, so the daily storage "
              "fill and the entry-point flows are the physical counterpart of every HU-I claim; "
              "storage is also the reason a Hungarian winter gas call is a STOCK decision and "
              "not only a flow one"),
    source_class(
        "hu_industry_logistics", "Vehicle and battery plant output, MAV freight, the MOL group's "
                                 "disclosed refining runs, and the customs trade detail -- the "
                                 "physical counterpart of a landlocked manufacturing economy",
        layer="physical_economy",
        roots=("https://www.ksh.hu/stadat_files/ipa/hu/ipa0008.html",
               "https://www.mavcsoport.hu", "https://molgroup.info/hu/befektetoi-kapcsolatok"),
        queries=("járműgyártás termelése", "akkumulátorgyár beruházás",
                 "vasúti árufuvarozás statisztika", "finomítói feldolgozás mennyisége",
                 "kőolajimport vezetéken", "ipari energiafelhasználás"),
        languages=("hu",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public (issuer disclosure for the refiner)",
        notes="HUNGARY IS LANDLOCKED and has no port authority, which is the one genuine "
              "physical absence in this pack; the layer is built on pipelines, storage, rail "
              "and plant-level output instead of berths and AIS. The refiner is an ACTOR and "
              "its disclosure is a SERIES -- never a share CFD"),
    # ---- source graph
    source_class(
        "hu_source_graph", "Who cites whom: MNB → Portfolio and the bank desks → hvg and Telex "
                           "→ the retail forums; the government decision → Magyar Közlöny → "
                           "MEKH's tariff → the utility bill; the Commission → MTI → the "
                           "domestic political read", layer="source_graph",
        roots=("https://www.portfolio.hu", "https://telex.hu/gazdasag", "https://mti.hu"),
        queries=("értesüléseink szerint", "kormányzati forrás szerint", "a Portfolio "
                 "információi szerint", "mint arról korábban beszámoltunk",
                 "a lapunk birtokába került tervezet", "nem hivatalos értesülés"),
        languages=("hu",), access_label="PUBLIC", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="derived from the public sources above",
        notes="'a lapunk birtokába került tervezet' marks the leaked draft decree that precedes "
              "a Hungarian price cap or sectoral tax by days; the graph is how a leak is told "
              "from a repost, and it is the only way to date an HU-G measure before the gazette "
              "prints it"),
)

#: NO LAYER IS ABSENT FOR HUNGARY, and that is a MEASUREMENT rather than an omission. Every one
#: of the ten has a real root above: an open-data central bank with a long time-series library,
#: an open statistical database, a digitised gazette with time-stamped consolidated law, an
#: active native-language retail and practitioner ground and two grid transparency platforms.
#: The one genuine physical absence -- the country is landlocked and has no port authority -- is
#: named INSIDE the physical-economy layer (`hu_industry_logistics`) rather than used to declare
#: the layer empty, because the layer is not empty: it is built on pipelines, storage and rail.
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


#: NATIVE QUERY TERRITORIES -- what the deep-forest miner types into a Hungarian search box, one
#: territory per layer. Not the source rows' queries repeated: these are the broader phrases a
#: crawler expands a layer with when it is hunting grounds this pack has not named yet.
QUERY_TERRITORIES: dict[str, tuple[str, ...]] = {
    "official": ("Monetáris Tanács kamatdöntése közlemény", "MNB egynapos betéti tender "
                 "eredménye", "KSH gyorstájékoztató fogyasztói árak",
                 "ÁKK aukciós naptár negyedév", "Magyar Közlöny kormányrendelet hatósági ár",
                 "MEKH határozat egyetemes szolgáltatás"),
    "institutional": ("Budapesti Értéktőzsde kereskedési naptár", "BUX index súlyok",
                      "Bankszövetség állásfoglalás különadó", "elemzői konszenzus kamatdöntés",
                      "KELER elszámolási szabályzat", "tőzsdei forgalom havi statisztika"),
    "academic": ("devizahitelezés makrogazdasági hatása tanulmány",
                 "forintosítás értékelése kutatás", "monetáris transzmisszió Magyarország",
                 "MNB-tanulmányok kamatpolitika", "REKK gázpiaci tanulmány",
                 "uniós források növekedési hatása elemzés"),
    "practitioner": ("Portfolio elemzés forint árfolyam", "állampapír aukció kommentár",
                     "heti makrogazdasági összefoglaló", "lakossági állampapír hozam elemzés",
                     "energiaár előrejelzés Magyarország", "kamatvárakozások FRA piac"),
    "retail_ecology": ("hova fektessem a megtakarításomat fórum", "euró vagy forint megtakarítás",
                       "állampapír vagy banki betét vita", "devizahiteles per tapasztalat",
                       "tőzsdézés kezdőknek fórum", "infláció elleni védekezés megtakarítás"),
    "app_ecosystem": ("MNB árfolyam webszolgáltatás lekérdezés", "KSH STADAT adatletöltés",
                      "WebKincstár állampapír vásárlás", "azonnali átutalás rendszer",
                      "értékpapír app díjak összehasonlítása", "nyílt adat portál Magyarország"),
    "media": ("MTI közlemény gazdaság", "hvg gazdaság elemzés forint",
              "Telex gazdaság uniós források", "24.hu gazdasági hírek energia",
              "Index gazdaság kamatdöntés", "kormányinfó gazdasági bejelentés"),
    "archive": ("Magyar Közlöny korábbi lapszám", "MNB történeti idősor letöltés",
                "KSH statisztikai évkönyv archívum", "Arcanum digitális tudománytár gazdaság",
                "országgyűlési napló költségvetési vita", "hatályos szöveg időállapot 2022"),
    "physical_economy": ("gáztároló telítettség napi adat", "FGSZ betáplálási pont forgalom",
                         "MAVIR rendszerterhelés adatok", "járműipari termelés havi adat",
                         "kőolajvezeték szállítás leállás", "akkumulátorgyár energiaigénye"),
    "source_graph": ("értesüléseink szerint kormányzati", "a lapunk birtokába került tervezet",
                     "a Portfolio információi szerint", "nem hivatalos kormányzati forrás",
                     "mint arról korábban beszámoltunk", "az MTI-nek nyilatkozó szakértő"),
}

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "MNB base rate decisions and the Monetary Council statements",
     "source": "Magyar Nemzeti Bank", "coverage": "1991 onward", "frequency": "monthly",
     "publication_lag_days": 0.0, "revisions": "never revised", "licence": "free, public",
     "history_from": "1991-01", "pit_feasible": True,
     "assets": ("EURHUF", "USDHUF", "EURPLN"),
     "mechanism_families": ("policy_surprise", "event_reaction"),
     "how_to_fetch": "mnb.hu Monetary Council statements plus the alapkamat time series; the "
                     "minutes land about two weeks later"},
    {"name": "MNB one-day and one-week deposit rates and their outstanding stock",
     "source": "Magyar Nemzeti Bank", "coverage": "2020 onward for the one-week; 2022-10-14 to "
                                                  "2023-09-26 for the one-day",
     "frequency": "daily during the regime", "publication_lag_days": 0.0,
     "revisions": "never", "licence": "free, public", "history_from": "2020-04",
     "pit_feasible": True, "assets": ("EURHUF", "USDHUF", "CHFHUF"),
     "mechanism_families": ("regime_break", "carry_funding"),
     "how_to_fetch": "the MNB statistical time-series library carries the tender rates and the "
                     "stock beside the base rate; THIS IS THE SERIES that makes the two-rate "
                     "regime reconstructible at all"},
    {"name": "MNB official forint exchange rates (the six crosses and the full basket)",
     "source": "Magyar Nemzeti Bank", "coverage": "1990 onward, every working day",
     "frequency": "daily", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "1990-01", "pit_feasible": True,
     "assets": ("EURHUF", "USDHUF", "CHFHUF", "GBPHUF"),
     "mechanism_families": ("fixing", "administered_price"),
     "how_to_fetch": "the MNB exchange-rate query web service; a long, stable, machine-readable "
                     "series that needs no scraper"},
    {"name": "MNB foreign exchange reserves, gold tonnage and the swap book",
     "source": "Magyar Nemzeti Bank", "coverage": "1995 onward", "frequency": "monthly",
     "publication_lag_days": 5.0, "revisions": "minor", "licence": "free, public",
     "history_from": "1995-01", "pit_feasible": True, "assets": ("XAUUSD", "EURHUF"),
     "mechanism_families": ("institutional_flow", "central_bank_balance_sheet"),
     "how_to_fetch": "mnb.hu statistics: the reserve series carries the 2014-2015 conversion "
                     "drawdown and the gold accumulation steps in one place"},
    {"name": "KSH consumer price index, core inflation and the regulated-energy line",
     "source": "Kozponti Statisztikai Hivatal", "coverage": "1992 onward",
     "frequency": "monthly", "publication_lag_days": 8.0, "revisions": "rebasing only",
     "licence": "free, public", "history_from": "1992-01", "pit_feasible": True,
     "assets": ("EURHUF", "USDHUF"),
     "mechanism_families": ("release_surprise", "administered_price"),
     "how_to_fetch": "ksh.hu gyorstajekoztatok plus the STADAT tables; the regulated-energy "
                     "line carries the utility price cap and its 2022 narrowing"},
    {"name": "KSH industrial production, including the vehicle and battery lines",
     "source": "Kozponti Statisztikai Hivatal", "coverage": "1998 onward",
     "frequency": "monthly", "publication_lag_days": 35.0, "revisions": "revised one month back",
     "licence": "free, public", "history_from": "1998-01", "pit_feasible": True,
     "assets": ("GER40", "EUSTX50", "EURHUF"),
     "mechanism_families": ("release_surprise", "transfer"),
     "how_to_fetch": "ksh.hu STADAT industrial tables; the vehicle line is the German chain "
                     "arriving as a Hungarian number and the battery line is the newest and "
                     "most energy-intensive part of it"},
    {"name": "KSH external trade by partner and product",
     "source": "Kozponti Statisztikai Hivatal", "coverage": "1992 onward",
     "frequency": "monthly", "publication_lag_days": 40.0, "revisions": "revised",
     "licence": "free, public", "history_from": "1992-01", "pit_feasible": True,
     "assets": ("GER40", "EURHUF", "XBRUSD"),
     "mechanism_families": ("trade_cycle", "transfer"),
     "how_to_fetch": "ksh.hu STADAT trade tables; the energy import line is where the Druzhba "
                     "exemption shows up as a physical quantity rather than a headline"},
    {"name": "AKK auction calendar, results and bid-to-cover",
     "source": "Allamadossag Kezelo Kozpont", "coverage": "1999 onward",
     "frequency": "weekly", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "1999-01", "pit_feasible": True,
     "assets": ("EURHUF", "USDHUF"),
     "mechanism_families": ("calendar_settlement", "supply_event"),
     "how_to_fetch": "akk.hu aukciok: the quarterly calendar in advance and the results the "
                     "same morning; bonds most often Thursday, bills most often Tuesday"},
    {"name": "AKK holder structure: the non-resident and the household share",
     "source": "Allamadossag Kezelo Kozpont", "coverage": "2003 onward", "frequency": "monthly",
     "publication_lag_days": 25.0, "revisions": "minor", "licence": "free, public",
     "history_from": "2003-01", "pit_feasible": True, "assets": ("EURHUF", "EURPLN"),
     "mechanism_families": ("positioning", "household_flow"),
     "how_to_fetch": "akk.hu statisztika: the two lines move AGAINST each other -- foreign "
                     "holders out, households in -- and that opposition is the object"},
    {"name": "Retail government securities: MAP Plusz volumes and rates",
     "source": "AKK and the Magyar Allamkincstar", "coverage": "2019 onward",
     "frequency": "weekly", "publication_lag_days": 7.0, "revisions": "never",
     "licence": "free, public", "history_from": "2019-06", "pit_feasible": True,
     "assets": ("EURHUF", "EUSTX50"),
     "mechanism_families": ("household_flow", "credit_channel"),
     "how_to_fetch": "allampapir.hu and the AKK weekly retail sales tables; the rate page "
                     "OVERWRITES IN PLACE, so the vintage is in the archive layer's crawls"},
    {"name": "European Commission and Council decisions on Hungarian EU funds",
     "source": "European Commission; Council of the EU; palyazat.gov.hu",
     "coverage": "2021 onward (RRF); 2022 onward (conditionality)",
     "frequency": "irregular, dated", "publication_lag_days": 1.0, "revisions": "never",
     "licence": "free, public", "history_from": "2021-01", "pit_feasible": True,
     "assets": ("EURHUF", "EURPLN", "EURCZK"),
     "mechanism_families": ("forced_flow", "political_event"),
     "how_to_fetch": "the Council press releases and the Commission's RRF payment decisions; "
                     "each suspension and release is a dated decision with a forced conversion "
                     "or its absence behind it"},
    {"name": "MEKH and gazette decrees on the utility price cap and the sectoral taxes",
     "source": "Magyar Kozlony / MEKH", "coverage": "2013 onward",
     "frequency": "irregular, dated", "publication_lag_days": 0.0,
     "revisions": "amended by decree", "licence": "free, public", "history_from": "2013-01",
     "pit_feasible": True, "assets": ("EURHUF", "XNGUSD"),
     "mechanism_families": ("administered_price", "release_surprise"),
     "how_to_fetch": "magyarkozlony.hu and njt.hu consolidated texts, which are TIME-STAMPED, "
                     "so what the cap said on any given day is recoverable exactly"},
    {"name": "Hungarian gas storage fill, entry-point flows and transmission capacity",
     "source": "FGSZ, the storage operator and ENTSOG", "coverage": "2011 onward, daily",
     "frequency": "daily", "publication_lag_days": 1.0, "revisions": "rarely",
     "licence": "free, public (registration for some feeds)", "history_from": "2011-01",
     "pit_feasible": True, "assets": ("XNGUSD", "GER40"),
     "mechanism_families": ("physical_supply", "energy_complex"),
     "how_to_fetch": "fgsz.hu information platform and the ENTSOG transparency API; storage is "
                     "large relative to demand here, so the winter gas call is a STOCK decision"},
    {"name": "MAVIR system load, generation and the import balance",
     "source": "MAVIR and the ENTSO-E transparency platform",
     "coverage": "2010 onward, quarter-hourly", "frequency": "continuous",
     "publication_lag_days": 0.0, "revisions": "outage notices amended",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": True,
     "assets": ("XNGUSD", "GER40", "EUSTX50"),
     "mechanism_families": ("physical_supply", "event_reaction"),
     "how_to_fetch": "mavir.hu data pages and transparency.entsoe.eu; Hungary runs a large "
                     "structural import balance, which is the state HU-I conditions on"},
    {"name": "MOL group disclosed refining runs, margins and crude slate",
     "source": "MOL Nyrt. investor disclosure", "coverage": "2005 onward",
     "frequency": "quarterly", "publication_lag_days": 45.0, "revisions": "rarely",
     "licence": "free, public (issuer disclosure)", "history_from": "2005-Q1",
     "pit_feasible": True, "assets": ("XBRUSD", "XNGUSD"),
     "mechanism_families": ("corporate_flow", "energy_complex"),
     "how_to_fetch": "the group's quarterly reports carry the crude slate and the realised "
                     "margin; THE GROUP IS AN ACTOR AND A SERIES -- never a share CFD "
                     "(two-lane order, 2026-09-06)"},
    {"name": "BUBOR fixings and the HUF money-market curve",
     "source": "Magyar Nemzeti Bank / the BUBOR panel", "coverage": "1996 onward",
     "frequency": "daily", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "1996-01", "pit_feasible": True,
     "assets": ("EURHUF", "USDHUF", "CHFHUF"),
     "mechanism_families": ("carry_funding", "fixing"),
     "how_to_fetch": "mnb.hu BUBOR pages; NOTE that BUBOR tracked the BASE rate during the "
                     "two-rate regime and therefore understated the real funding cost -- the "
                     "trap this pack exists partly to stop"},
    {"name": "The 2015 FX-loan conversion: fixed rates, volumes and the MNB tenders",
     "source": "MNB, the conversion acts and the banking-sector statistics",
     "coverage": "2014-11 to 2015-Q2", "frequency": "one dated episode",
     "publication_lag_days": 30.0, "revisions": "the sector aggregates were restated",
     "licence": "free, public", "history_from": "2014-11", "pit_feasible": True,
     "assets": ("CHFHUF", "EURHUF"),
     "mechanism_families": ("regime_break", "credit_channel"),
     "how_to_fetch": "the MNB's conversion communiques and the household loan stock by currency "
                     "in the statistical library; the boundary is what matters, not the level"},
    {"name": "The Hungarian work-schedule decrees: bridge rest days and working Saturdays",
     "source": "Magyar Kozlony ministerial decrees", "coverage": "2010 onward",
     "frequency": "annual, dated", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "2010-01", "pit_feasible": True,
     "assets": ("EURHUF", "EUSTX50", "GER40"),
     "mechanism_families": ("holiday_liquidity", "session_microstructure"),
     "how_to_fetch": "search magyarkozlony.hu for the annual munkaszuneti napok korüli munkarend "
                     "decree; NO RULE COMPUTES THESE and the pack carries them declared, with "
                     "2026 deliberately empty until the decree is read"},
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "The MNB Monetary Council (Monetaris Tanacs)",
     "holds": "the base rate, the interest-rate corridor, and the right to make something else "
              "the effective instrument whenever it chooses to",
     "forced_to": ("decide the base rate at a monthly rate-setting meeting on a published "
                   "calendar", "publish a statement the same afternoon and minutes two weeks "
                   "later", "publish a quarterly Inflation Report with a forecast",
                   "defend a published 3% target with a tolerance band"),
     "when": "the last Tuesday of the month, early afternoon Europe/Budapest -- but the "
             "effective rate was decided at a DAILY tender outside this calendar for eleven "
             "months in 2022-2023",
     "information": ("the staff forecast before the market sees it",
                     "the tender demand and the banking system's forint liquidity",
                     "the government's funding plan and its fiscal intentions",
                     "the state of the EU funds negotiation before it is announced"),
     "constraints": ("a published 3% target, which gives a surprise a natural scale",
                     "a secondary mandate to support government economic policy, which no "
                     "Czech or Polish counterpart carries in the same words",
                     "a forint that is the highest-yielding currency in the European Union and "
                     "therefore the region's funding and carry instrument",
                     "an inflation shock that was the largest in the EU in 2022-2023"),
     "instruments": ("EURHUF", "USDHUF", "EURPLN"),
     "counterparties": ("the banks at the deposit and swap tenders",
                        "the offshore accounts short forint for carry",
                        "the debt agency, whose funding cost it sets",
                        "the government, whose price caps it must forecast around"),
     "observables": ("the statement and the minutes",
                     "the base rate and, separately, the EFFECTIVE tender rate",
                     "the Inflation Report's forecast revision",
                     "the outstanding deposit stock, which says whether the rate bound"),
     "impact": "a decision moves all six HUF crosses at once, and the pack can decompose the "
               "move into the common forint factor and the cross-specific residual rather than "
               "guessing which one it was",
     "persistence": "the base-rate level persists between monthly meetings; the EFFECTIVE rate "
                    "in the two-rate regime persisted only until the next daily tender",
     "falsifier": "the decision window matches the four nearest non-meeting Tuesdays at the "
                  "same LOCAL clock, or matches ECB decision days -- in which case it is a "
                  "weekday effect or a euro event wearing the MNB's hat",
     "notes": "THE CALENDAR IS NOT THE EVENT LIST. A monthly meeting calendar misses the "
              "instrument that actually bound for eleven months, and that is the single most "
              "important fact about mining Hungarian policy"},
    {"name": "The MNB money-market desk as the two-rate regime's operator",
     "holds": "the overnight deposit quick tender that stood at 18% while the base rate stood "
              "at 13%, plus the one-week deposit and the discount bond",
     "forced_to": ("announce and allot the tender intraday, daily, outside the meeting calendar",
                   "publish the allotted stock, which is the measure of whether the rate bound",
                   "converge the instrument back to the base rate once the currency stabilised",
                   "explain a second policy rate that its own statements did not call one"),
     "when": "daily through the emergency regime from 2022-10-14; the convergence ran in steps "
             "from May 2023 and completed on 2023-09-26",
     "information": ("the banks' forint liquidity position in real time",
                     "the pressure on the forint before the market can see the intervention",
                     "the size of the position parked at the tender"),
     "constraints": ("a currency that had fallen to record lows against the euro",
                     "an inflation rate that was the highest in the EU",
                     "a need to raise the EFFECTIVE rate without a headline base-rate move",
                     "an eventual obligation to unwind the split without a currency relapse"),
     "instruments": ("EURHUF", "USDHUF", "CHFHUF"),
     "counterparties": ("the domestic banks parking liquidity at the tender",
                        "the offshore carry accounts whose funding cost it set",
                        "the exporters and importers whose hedging it repriced"),
     "observables": ("the daily tender rate and allotment",
                     "the outstanding overnight deposit stock",
                     "the gap between the tender rate and the base rate",
                     "BUBOR, which tracked the WRONG one"),
     "impact": "the real Hungarian carry for eleven months; a study that used the base rate "
               "understated the cost of a forint short by up to five percentage points",
     "persistence": "the regime lasted eleven months and ended on a dated decision",
     "falsifier": "the tender rate carries no information about the six crosses beyond the base "
                  "rate over the same window -- in which case the split was cosmetic",
     "notes": "THE REASON HU-B IS ITS OWN DOMAIN: two rates, one currency, one dated boundary "
              "at each end, and a whole literature that pooled straight across it"},
    {"name": "The MNB FX swap desk",
     "holds": "the EUR/HUF swap tenders and the forint liquidity they move",
     "forced_to": ("announce the tenders on its own schedule rather than the meeting calendar",
                   "publish the allotment and the swap book's size in the reserve statistics",
                   "supply the foreign currency for the 2015 household loan conversion out of "
                   "reserves rather than let it be bought in the market"),
     "when": "irregular and announced; concentrated in stress episodes and in the conversion "
             "window of late 2014 and early 2015",
     "information": ("the banks' forint and FX liquidity mismatch",
                     "the size of the conversion demand before it hit the market",
                     "its own reserve adequacy calculation"),
     "constraints": ("a reserve stock that the conversion drew down visibly",
                     "a swap instrument that moves forward points without moving spot, which "
                     "means the OBSERVABLE is the swap point and not the rate",
                     "no published tenor breakdown of the book"),
     "instruments": ("EURHUF", "USDHUF", "CHFHUF"),
     "counterparties": ("the domestic banks", "the foreign banks funding forint positions",
                        "the households whose FX loans were converted, indirectly"),
     "observables": ("the tender announcements and allotments",
                     "the swap points against the interest differential",
                     "the reserve series' drawdown in the conversion window"),
     "impact": "the instrument that let Hungary convert a household FX-loan book without buying "
               "the currency in the market -- the clearest case on this desk of a central bank "
               "removing a transmission channel by balance-sheet operation",
     "persistence": "an episode lasts weeks; the CHANNEL REMOVAL was permanent",
     "falsifier": "swap tender dates carry no EURHUF or CHFHUF effect beyond the rate "
                  "differential already in the forward points",
     "notes": "the mechanism behind HU-C and the operational half of HU-F"},
    {"name": "The MNB reserve management and the gold programme",
     "holds": "the reserve portfolio and a gold stock taken from about three tonnes to more "
              "than a hundred in a small number of announced steps",
     "forced_to": ("publish the reserve headline and the gold tonnage monthly",
                   "announce the large gold increases, which it has done each time",
                   "hold enough reserves to satisfy its own published adequacy rules"),
     "when": "the gold steps were announced and dated; the monthly series is published a few "
             "business days after the month end",
     "information": ("the purchase before it is disclosed",
                     "its own adequacy calculation and its tolerance for reserve drawdown"),
     "constraints": ("a reserve stock already drawn down by the 2015 conversion",
                     "a political framing of gold as a sovereignty asset, which makes the "
                     "programme sticky rather than tactical",
                     "monthly disclosure only, so the flow is inferable and never live"),
     "instruments": ("XAUUSD", "EURHUF"),
     "counterparties": ("the bullion market", "the other official-sector buyers",
                        "the domestic political audience the announcements are made to"),
     "observables": ("the announced step and its date", "the monthly tonnage",
                     "the reserve headline in euro"),
     "impact": "a disclosed, price-insensitive official buyer whose purchases arrive in a "
               "handful of large, dated steps rather than as a smooth programme -- a different "
               "shape from the Czech monthly ramp and testable against it",
     "persistence": "each step is permanent; the programme has run for years",
     "falsifier": "announced Hungarian gold steps show no XAUUSD effect beyond the aggregate "
                  "official-sector purchase series",
     "notes": "the cross-pack test is the interesting one: two CEE central banks buying gold "
              "with two different execution shapes, and only one of them can be the reason "
              "XAUUSD moved"},
    {"name": "AKK Zrt., the government debt agency",
     "holds": "the wholesale bond and bill programme, the euro issuance and the largest retail "
              "government securities programme in the region",
     "forced_to": ("publish a quarterly issuance calendar in advance",
                   "auction on that calendar and publish the results the same morning",
                   "publish the holder structure monthly",
                   "sell retail paper continuously at a published rate"),
     "when": "bonds most often on Thursdays, bills most often on Tuesdays, results before noon "
             "local; the retail programme sells every working day",
     "information": ("the primary dealers' indications before the auction",
                     "the retail subscription run-rate before it is published",
                     "the state's cash position"),
     "constraints": ("a retail programme that competes with its own wholesale curve and with "
                     "bank deposits at the same time",
                     "a non-resident holder base that has shrunk as the household one grew",
                     "a funding cost set by a central bank with two policy rates"),
     "instruments": ("EURHUF", "USDHUF", "EURPLN"),
     "counterparties": ("the primary dealers", "the Hungarian household, directly",
                        "the non-resident accounts whose share it publishes"),
     "observables": ("the issuance calendar", "the auction cut-off and bid-to-cover",
                     "the monthly holder structure's two opposing lines",
                     "the retail sales run-rate"),
     "impact": "a weak auction lifts the HUF curve and pressures the six crosses the same "
               "morning; the retail programme is a domestic savings sink that changes who owns "
               "the currency risk",
     "persistence": "an auction effect is intraday to a few days; the HOLDER SHIFT is a "
                    "multi-year structural change",
     "falsifier": "auction mornings are indistinguishable from the matched non-auction weekday "
                  "in the same week across all six crosses",
     "notes": "the household share of Hungarian government debt is far larger than in Czechia "
              "or Poland, which is a genuine structural difference and not a rounding one"},
    {"name": "The Hungarian government as the price-cap and sectoral-tax authority",
     "holds": "the household utility price cap, the food price caps, the fuel price cap while "
              "it lasted, and a series of sectoral extra-profit taxes",
     "forced_to": ("publish every measure as a decree in Magyar Kozlony",
                   "set a date from which each applies", "renew or let each one lapse, on a "
                   "date", "fund the difference between the capped and the market price"),
     "when": "irregular and dated, often announced at a government press briefing and gazetted "
             "within days; the utility cap has been in force since 2013 and was NARROWED on "
             "2022-08-01",
     "information": ("the draft decree before it is gazetted, which leaks to the press",
                     "the fiscal cost of the cap before it is published",
                     "the political tolerance for a price step"),
     "constraints": ("a fiscal cost that rises with the market price it is capping",
                     "EU state-aid and internal-market limits",
                     "an inflation print that the cap suppresses and then releases",
                     "a gazette that makes every measure citable and dated"),
     "instruments": ("EURHUF", "XNGUSD", "USDHUF"),
     "counterparties": ("the household, who pays the capped price",
                        "the utilities and the banks, who pay the difference or the tax",
                        "the MNB, which must forecast around a price it does not set"),
     "observables": ("the gazette decree and its date",
                     "the capped tariff and the threshold above which the market price applies",
                     "the CPI line the measure lands in",
                     "the leaked draft in the press a day or two earlier"),
     "impact": "the largest single administered component of Hungarian inflation, switched by "
               "decree, with a leak that usually precedes it",
     "persistence": "a cap persists until it is changed; the 2022 narrowing was a permanent "
                    "regime change in the household energy price",
     "falsifier": "CPI surprises in the months after a cap change are uncorrelated with the "
                  "size of the change, which would mean the market prices it perfectly",
     "notes": "this actor has no Czech equivalent: the ERU sets a REGULATED component by "
              "methodology, while this sets a CAPPED price by decree"},
    {"name": "KSH, the Central Statistical Office, as the release clock",
     "holds": "the CPI, industrial production, trade and GDP prints and the calendar that dates "
              "them",
     "forced_to": ("publish on a calendar announced a year ahead",
                   "release at 08:30 local, which is half an hour BEFORE the German 08:00 CET "
                   "prints on the winter clock",
                   "serve the data through an open database",
                   "revise on a published schedule"),
     "when": "08:30 Europe/Budapest on the calendar date; CPI early in the month, industrial "
             "production about five weeks after the reference month",
     "information": ("the print before the market", "the revision before publication"),
     "constraints": ("an EU statistical framework that fixes definitions",
                     "a small open economy with noisy monthly series",
                     "an inflation basket in which an administered price is a large weight"),
     "instruments": ("EURHUF", "USDHUF", "GER40"),
     "counterparties": ("Eurostat", "the MNB's forecasting staff",
                        "the bank desks that publish the consensus"),
     "observables": ("the release calendar", "the print and its revision",
                     "the STADAT machine-readable tables"),
     "impact": "the CPI print has a published target behind it, so its surprise has a natural "
               "scale -- and on the winter clock it is readable HALF AN HOUR BEFORE the German "
               "releases, which is an ordering advantage no other CEE pack has",
     "persistence": "a print's effect is intraday to a day",
     "falsifier": "the Hungarian print window is indistinguishable from the same local clock "
                  "time on non-release days once the German prints are controlled for",
     "notes": "`release_minute_utc` is the function that keeps the ordering straight across the "
              "DST boundary, where the advantage disappears"},
    {"name": "MOL as the Druzhba-exempt refiner",
     "holds": "the Hungarian and Slovak refining system and a crude slate that has included "
              "pipeline crude exempted from the EU's seaborne import ban",
     "forced_to": ("disclose its crude slate, runs and realised margin as a listed bond issuer",
                   "pay the sectoral extra-profit taxes the government levies on the spread",
                   "keep supplying a capped domestic fuel price while it was in force",
                   "invest to be able to process non-Russian grades"),
     "when": "quarterly disclosure; the policy events -- the exemption, the taxes, the fuel cap "
             "-- are dated decrees and Council decisions",
     "information": ("its own crude purchase cost before the market sees the margin",
                     "the pipeline's operational state before the outage is public"),
     "constraints": ("a pipeline whose upstream end is outside EU jurisdiction",
                     "a tax that captures much of the discount it earns",
                     "an EU exemption that is political and revocable",
                     "a domestic price cap that removed its retail pricing power"),
     "instruments": ("XBRUSD", "XNGUSD", "EURHUF"),
     "counterparties": ("the pipeline operator and the crude seller",
                        "the Hungarian state as tax authority and price-setter",
                        "the European refiners who do not have the exemption"),
     "observables": ("the disclosed crude slate and refining margin",
                     "the customs energy import line by pipeline",
                     "the gazetted tax and cap decrees",
                     "the pipeline interruption reports"),
     "impact": "a discount other European refiners cannot get, taxed away in part, and a "
               "measurable divergence between a Hungarian refining margin and a European one",
     "persistence": "the exemption has persisted for years and is revocable on a political date",
     "falsifier": "the Hungarian energy import line and the disclosed margin add nothing to a "
                  "Brent-based model of the European refining margin",
     "notes": "AN ACTOR AND A SERIES, NEVER AN INSTRUMENT: the two-lane order forbids hunting "
              "the share, and no share CFD appears anywhere in this pack"},
    {"name": "MVM and the Paks II nuclear decision",
     "holds": "the state energy group, the existing nuclear plant that supplies a large share of "
              "domestic generation, and a decade-long Russian-financed expansion project",
     "forced_to": ("keep the existing units available and declare their outages",
                   "import the balance of electricity Hungary does not generate",
                   "buy gas under long-term contracts and fill the storage each summer",
                   "report the project's milestones, which slip"),
     "when": "outages are declared in advance; the storage fill is a summer programme; the "
             "project milestones are announced and repeatedly revised",
     "information": ("the maintenance plan before the notice",
                     "the long-term contract terms, which are not public",
                     "the storage injection schedule"),
     "constraints": ("a structural electricity import balance",
                     "a landlocked gas position with large storage and few entry points",
                     "a project financed and supplied under an intergovernmental agreement",
                     "EU energy policy pulling the other way"),
     "instruments": ("XNGUSD", "GER40", "EUSTX50"),
     "counterparties": ("the neighbouring grids Hungary imports from",
                        "the gas suppliers and the storage operator",
                        "the state as owner and as financier"),
     "observables": ("the ENTSO-E outage notices and the MAVIR import balance",
                     "the daily storage fill",
                     "the gazette and ministry announcements on the project"),
     "impact": "a nuclear outage raises the import balance and the gas call at once, and the "
               "storage level decides whether a winter call is urgent or not",
     "persistence": "an outage is weeks; the storage cycle is annual; the project is a decade",
     "falsifier": "Hungarian outage and storage states carry nothing for XNGUSD beyond the "
                  "European storage aggregate and the German price",
     "notes": "AN ACTOR AND NEVER AN INSTRUMENT; the executable leg is the gas benchmark"},
    {"name": "The European Commission and Council as the conditionality authority",
     "holds": "the cohesion envelope and the RRF tranches, and the legal mechanism to suspend "
              "them",
     "forced_to": ("assess against published milestones and publish the assessment",
                   "take suspension and release decisions in public, on dates",
                   "pay in EUR, which the member state must convert",
                   "negotiate with a government that treats the negotiation as domestic "
                   "politics"),
     "when": "irregular and dated; decisions cluster around European Council meetings and "
             "quarter boundaries",
     "information": ("the assessment before publication",
                     "the political bargain being struck alongside it"),
     "constraints": ("its own published rules and milestones",
                     "a Council that can overrule the technocratic reading",
                     "unanimity requirements elsewhere that give the member state leverage"),
     "instruments": ("EURHUF", "EURPLN", "EURCZK"),
     "counterparties": ("the Hungarian government", "the other member states",
                        "the Polish government, whose parallel case moved on its own timeline"),
     "observables": ("the published decisions and their dates",
                     "the Hungarian payment requests",
                     "the forint's move on decision days",
                     "the political-risk premium between decisions"),
     "impact": "THE CLEANEST POLITICAL EVENT SERIES ON THIS DESK: dated, published, binary, and "
               "with a large forced conversion behind each release",
     "persistence": "a suspension persists for quarters; a release is a one-off conversion with "
                    "a persistent premium change behind it",
     "falsifier": "decision dates carry no EURHUF effect once quarter-end and the euro tape are "
                  "controlled for, and EURCZK -- the leg with no political discount -- moves "
                  "the same way",
     "notes": "Czechia is the control here, which is exactly why the two packs declare each "
              "other in INTERACTIONS"},
    {"name": "The Hungarian household as FX-loan debtor turned retail bondholder",
     "holds": "a mortgage book converted out of Swiss francs in 2015 and, since 2019, the "
              "largest retail government bond holding in the region",
     "forced_to": ("accept the 2015 conversion at administratively fixed rates",
                   "choose every month between a bank deposit, an inflation-linked retail bond "
                   "and euro cash",
                   "pay a capped energy price and a market price above the threshold"),
     "when": "the conversion was a single dated episode; the savings choice is continuous and "
             "its episodes are dated by the retail sales run-rate",
     "information": ("nothing the market does not have; this actor is a FOLLOWER and is "
                     "modelled as one",
                     "its own bill, which is where an administered price becomes politics"),
     "constraints": ("an inflation rate that was the highest in the EU",
                     "a retail bond that pays more than any deposit on offer",
                     "ESMA leverage caps on any margin account"),
     "instruments": ("EURHUF", "EUSTX50", "XAUUSD"),
     "counterparties": ("the banks", "the Treasury's retail network",
                        "the exchange bureaux, for euro cash"),
     "observables": ("the weekly retail bond sales", "the deposit and fund flow statistics",
                     "the AKK household share of debt",
                     "the forum and search vocabulary at the turning points"),
     "impact": "large in aggregate: the household bid is why the non-resident share of "
               "Hungarian debt could fall without a funding crisis",
     "persistence": "a migration episode lasts quarters",
     "falsifier": "retail bond sales are explained by the rate level alone with no residual the "
                  "retail vocabulary dates",
     "notes": "kept at LOW WEIGHT and never a source of edge"},
    {"name": "The Hungarian commercial banks under sectoral taxes and rate caps",
     "holds": "the deposit base, the converted mortgage book and the profits the state taxes",
     "forced_to": ("pass a policy rate into deposits at a speed the state has repeatedly "
                   "legislated about",
                   "absorb extra-profit taxes announced by decree",
                   "observe interest-rate caps and payment moratoria when they are imposed",
                   "compete with a state retail bond paying more than they do"),
     "when": "continuously; the tax and cap events are dated decrees",
     "information": ("its own deposit migration before the aggregate shows it",
                     "the draft decree, through the association, before it is gazetted"),
     "constraints": ("a state that legislates its pricing",
                     "a household that can move to retail government paper instantly",
                     "foreign parent groups that must explain Hungarian taxes to their own "
                     "shareholders"),
     "instruments": ("EURHUF", "EUSTX50", "GER40"),
     "counterparties": ("the household", "the MNB at the tenders",
                        "the state as tax authority", "the foreign parents"),
     "observables": ("the gazetted tax and cap decrees",
                     "the deposit rate against the policy rate",
                     "the association's published objections",
                     "the parents' disclosures of the Hungarian charge"),
     "impact": "the transmission from a policy rate to a household rate is politically mediated "
               "here in a way it is not in Czechia, which is a real difference between two "
               "neighbouring credit channels",
     "persistence": "a tax lasts a budget year and is usually renewed",
     "falsifier": "Hungarian deposit-rate pass-through matches the Czech and Polish pass-through "
                  "once the policy rate is controlled for, leaving nothing for the politics",
     "notes": "the banks are ACTORS; no share CFD for any of them appears in this pack"},
    {"name": "The offshore forint carry account",
     "holds": "short-forint positions funded in euro, Swiss franc or yen, or long-forint carry "
               "positions when the effective rate was 18%",
     "forced_to": ("fund at the EFFECTIVE rate, not the base rate",
                   "hold a currency whose political risk premium is switched by EU decisions",
                   "unwind into the same liquidity that built the position"),
     "when": "continuous; the crowding episodes are dated by the record forint lows of 2022 and "
             "by the conditionality decisions",
     "information": ("its own size, which nobody outside it knows",
                     "the crowding, visible only in the six-cross correlation structure and in "
                     "the AKK holder table"),
     "constraints": ("no COT series exists for the forint, so the position is never directly "
                     "observed", "a funding cost that was two different numbers for eleven "
                     "months", "a political event calendar it cannot hedge"),
     "instruments": ("EURHUF", "AUDHUF", "NZDHUF", "CHFHUF"),
     "counterparties": ("the domestic banks", "the MNB at the tenders", "each other"),
     "observables": ("the common factor across all six crosses",
                     "the AKK non-resident share",
                     "the swap points against the interest differential",
                     "the speed of the move on political headlines"),
     "impact": "the six-cross panel is how this actor is measured at all: a move common to "
               "EURHUF, USDHUF, AUDHUF, CHFHUF, GBPHUF and NZDHUF is the forint; a move in one "
               "is the other leg",
     "persistence": "positions build over quarters and unwind in days",
     "falsifier": "the common factor across the six crosses adds nothing to EURHUF alone -- in "
                  "which case the panel is redundant and this pack's structural advantage is "
                  "imaginary",
     "notes": "THE SUBSTITUTE FOR A COT REPORT THAT DOES NOT EXIST, and it is a better one: six "
              "simultaneous prices rather than one weekly survey"},
    {"name": "The Budapest Stock Exchange and KELER",
     "holds": "the BUX index, the trading calendar, the settlement cycle and the turnover "
              "statistics",
     "forced_to": ("publish a trading calendar that follows the statutory holidays AND the "
                   "decreed rest days", "run a closing auction every session",
                   "settle through KELER", "publish turnover and the foreign share"),
     "when": "09:00-17:05 local continuous with a closing call, on every day the decree does "
             "not make a rest day",
     "information": ("the closing auction imbalance before the print",
                     "the member-level turnover before aggregation"),
     "constraints": ("an index that is four names",
                     "central-bank majority ownership of the exchange since 2015",
                     "a thin listed derivatives market with no deep expiry clock"),
     "instruments": ("EUSTX50", "GER40", "EURHUF"),
     "counterparties": ("the MNB as owner", "the domestic pension funds",
                        "the foreign brokers routing flow"),
     "observables": ("the BUX level and turnover", "the foreign turnover share",
                     "the trading calendar including the decreed rest days"),
     "impact": "BOUNDED BY CONSTRUCTION: no BUX CFD exists and the index is four names, so this "
               "is a mechanics domain about the calendar and the settlement clock",
     "persistence": "the microstructure facts persist for years",
     "falsifier": "the Hungarian session and settlement clock carries nothing for EUSTX50 or "
                  "EURHUF beyond the euro-area session itself",
     "notes": "the honest ceiling on HU-L is stated rather than discovered later"},
    {"name": "The ministry that moves the working calendar by decree",
     "holds": "the annual work-schedule decree that turns a weekday into a rest day and a "
              "Saturday into a working day",
     "forced_to": ("publish the decree in Magyar Kozlony in the preceding year",
                   "keep the total number of working days unchanged, which is WHY a Saturday "
                   "must be worked for every bridge day granted"),
     "when": "the decree is gazetted in the preceding year; the swapped days themselves fall "
             "around the statutory holidays",
     "information": ("the draft, which is usually reported before it is gazetted",
                     "the total working-day count it has to preserve"),
     "constraints": ("a working-time total it must preserve",
                     "a Labour Code that grants no weekend substitution, so the swaps are the "
                     "only flexibility available"),
     "instruments": ("EURHUF", "EUSTX50", "GER40"),
     "counterparties": ("every employer and every bank back office",
                        "the exchange, which closes on the rest days",
                        "the neighbouring markets, which do neither"),
     "observables": ("the gazetted decree", "the exchange's trading calendar",
                     "the working Saturdays, which are real domestic sessions with no European "
                     "counterpart at all"),
     "impact": "a Hungarian working Saturday is the only day in the CEE calendar when one "
               "country's corporates and banks are at work and every neighbouring market is "
               "shut -- a genuinely unique liquidity state",
     "persistence": "one year at a time, by decree",
     "falsifier": "bridge rest days and working Saturdays are indistinguishable from matched "
                  "ordinary days on every spread and range measure",
     "notes": "NO RULE COMPUTES THESE. They are declared in SWAPPED_DAYS with a status, and "
              "2026 is deliberately empty until the decree is read (L1.28a)"},
)

# --------------------------------------------------------------------------- domains
#: Each domain carries `mechanism_family` and `horizon` beside the framework's four required
#: fields, because `cells()` mints one testable cell per (domain x instrument x condition).
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "HU-A", "title": "The MNB monthly rate decision and the published target",
     "objects": ("the last-Tuesday rate decisions and the statements",
                 "the minutes two weeks later and the forecast revision",
                 "the Inflation Report's quarterly projection",
                 "the analyst consensus the domestic press polls"),
     "conditions": ("a meeting inside the two-rate regime, when the base rate was NOT the "
                    "effective instrument, against one outside it",
                    "the DST regime, which moves the same local announcement between two UTC "
                    "minutes",
                    "the distance of the CPI print from the 3% target at the meeting"),
     "instruments": ("EURHUF", "USDHUF", "EURPLN"),
     "controls": ("the four nearest non-meeting Tuesdays at the same LOCAL clock",
                  "ECB decision days over the same window, separating 'the euro moved' from "
                  "'the MNB decided'",
                  "EURPLN and EURCZK as the CEE peer null"),
     "mechanism_family": "central_bank_surprise", "horizon": "intraday",
     "notes": "the monthly calendar is NOT the full Hungarian policy event list; see HU-B"},
    {"id": "HU-B", "title": "The two-rate regime: an 18% one-day deposit above a 13% base rate",
     "objects": ("the 2022-10-14 introduction and the 2023-09-26 merger",
                 "the daily tender rate and the allotted stock",
                 "the monthly convergence steps from May 2023",
                 "BUBOR, which tracked the base rate and not the tender"),
     "conditions": ("inside the regime against outside it -- the single most important "
                    "conditioning state in this pack",
                    "the SPREAD between the tender rate and the base rate, which was as wide as "
                    "five percentage points",
                    "the size of the outstanding overnight deposit stock, which says whether "
                    "the rate bound or was decorative"),
     "instruments": ("EURHUF", "USDHUF", "CHFHUF"),
     "controls": ("EURPLN and EURCZK over the identical windows: neither neighbour ran a split "
                  "rate, so anything common to all three is regional",
                  "the same carry statistic computed on the BASE rate, which is the error this "
                  "domain exists to measure",
                  "the pre-2022 window, where the state could not vary"),
     "mechanism_family": "regime_break", "horizon": "multi_day",
     "notes": "WHAT THIS REGIME INVALIDATES is enumerated in TWO_RATE_REGIME and must be "
              "carried into any Hungarian carry or policy study that spans it"},
    {"id": "HU-C", "title": "The MNB's FX swap tenders and the forward points",
     "objects": ("the announced swap tenders and their allotments",
                 "the swap points against the interest differential",
                 "the reserve series' drawdown in the 2014-2015 conversion window",
                 "the stress episodes the tenders cluster in"),
     "conditions": ("a tender announced in the window against no tender",
                    "the sign of the deviation between the swap points and the differential",
                    "whether the episode was a conversion operation or a liquidity one"),
     "instruments": ("EURHUF", "USDHUF", "CHFHUF"),
     "controls": ("the same deviation measured on EURPLN, where no comparable tender programme "
                  "exists",
                  "matched non-tender days in the same month",
                  "a randomised-date null on the tender announcements"),
     "mechanism_family": "carry_funding", "horizon": "session",
     "notes": "the swap moves FORWARD POINTS without moving spot, so the observable is the "
              "basis and not the rate -- a study that looks at spot alone will find nothing"},
    {"id": "HU-D", "title": "The six-cross panel: the forint factor against the cross residual",
     "objects": ("simultaneous returns on EURHUF, USDHUF, AUDHUF, CHFHUF, GBPHUF and NZDHUF",
                 "the first principal component of the six as the forint factor",
                 "the cross-specific residuals as the funding legs' own stories",
                 "the AKK non-resident share as the only published positioning proxy"),
     "conditions": ("a move common to all six against a move in one or two",
                    "the carry regime: which of the six legs was the cheapest funding currency",
                    "a political-event day against an ordinary day"),
     "instruments": ("EURHUF", "USDHUF", "AUDHUF", "CHFHUF", "GBPHUF", "NZDHUF"),
     "controls": ("the same decomposition on the funding legs alone -- AUDNZD and EURUSD -- "
                  "which must explain the residual if the forint factor is real",
                  "EURPLN and EURCZK, which have no six-cross panel and must move with the "
                  "common factor if it is regional rather than Hungarian",
                  "a block-permuted panel as the null for a factor structure"),
     "mechanism_family": "positioning", "horizon": "multi_day",
     "notes": "THE STRUCTURAL REASON THIS PACK EXISTS. No COT series exists for HUF; six "
              "simultaneous prices are a better substitute than one weekly survey would be"},
    {"id": "HU-E", "title": "EU funds conditionality as a dated political event",
     "objects": ("the conditionality trigger, the Council suspension and the release decisions",
                 "the RRF payment requests and the milestone assessments",
                 "the forint's move on decision days",
                 "the premium between EURHUF and EURCZK between decisions"),
     "conditions": ("a suspension decision against a release decision against an ordinary day",
                    "the size of the tranche relative to monthly FX turnover",
                    "whether the decision was anticipated by a leak in the press"),
     "instruments": ("EURHUF", "EURCZK", "EURPLN"),
     "controls": ("EURCZK, the leg with NO political discount in it, over the identical windows",
                  "quarter-end windows in quarters with no decision",
                  "a randomised-date null on the decision dates"),
     "mechanism_family": "forced_flow", "horizon": "multi_day",
     "notes": "the cleanest political event series on this desk: dated, published, binary, and "
              "with a large forced conversion behind each release"},
    {"id": "HU-F", "title": "The 2015 forint conversion and what it removed from the beta",
     "objects": ("the 2014-11-07 announcement and the 2015-02-01 effective date",
                 "the household loan stock by currency before and after",
                 "the MNB's conversion tenders and the reserve drawdown",
                 "the CHFHUF relationship on either side of the boundary"),
     "conditions": ("before the conversion against after it",
                    "the size of the outstanding FX loan stock in the window",
                    "episodes of CHF strength, which is when the removed loop would have bitten"),
     "instruments": ("CHFHUF", "EURHUF", "USDHUF"),
     "controls": ("CHFPLN's Polish twin, where the FX-mortgage stock was NOT converted and the "
                  "loop is still live: the difference IS the mechanism",
                  "the same statistics on EURHUF, which had a much smaller FX-loan channel",
                  "the pre-2010 window, before the FX-loan stock was large"),
     "mechanism_family": "regime_break", "horizon": "multi_day",
     "notes": "CHFPLN is not quoted here, so the Polish control runs through EURPLN and the pl "
              "pack -- which is exactly what the INTERACTIONS row with pl is for"},
    {"id": "HU-G", "title": "The utility price cap and the administered inflation print",
     "objects": ("the gazetted cap decrees since 2013 and the 2022-08-01 narrowing",
                 "the capped tariff and the above-threshold market price",
                 "the regulated-energy weight in the CPI basket",
                 "the leaked draft that usually precedes a decree"),
     "conditions": ("a cap change in the window against none",
                    "the gap between the capped price and the prevailing market price",
                    "whether a leak preceded the gazette"),
     "instruments": ("EURHUF", "XNGUSD", "USDHUF"),
     "controls": ("the non-regulated CPI components over the same months as the internal "
                  "placebo",
                  "the Czech regulated-energy step in the same window, which is set by "
                  "methodology rather than by decree",
                  "months with a gazetted decree that did not change a price"),
     "mechanism_family": "administered_price", "horizon": "multi_day",
     "notes": "the 2022 narrowing was the single largest Hungarian inflation event of the "
              "decade and it has a gazette date"},
    {"id": "HU-H", "title": "The Druzhba exemption and the Hungarian refining margin",
     "objects": ("the pipeline-crude exemption and the decisions that preserved it",
                 "the disclosed crude slate and realised refining margin",
                 "the customs energy import line by transport mode",
                 "the sectoral extra-profit tax that captures part of the spread"),
     "conditions": ("a pipeline interruption or a sanctions decision in the window",
                    "the level of the crude benchmark, since the discount is a spread on it",
                    "whether the extra-profit tax was in force at the rate it now is"),
     "instruments": ("XBRUSD", "XNGUSD", "EURHUF"),
     "controls": ("the European refining margin over the same quarters, which has no exemption",
                  "quarters with no sanctions or pipeline event",
                  "the Slovak and Czech refining systems, which share the pipeline"),
     "mechanism_family": "energy_complex", "horizon": "multi_day",
     "notes": "the discount ITSELF is a LICENSED assessment and unreadable here, so the domain "
              "is measured on the executable benchmark and the disclosed margin"},
    {"id": "HU-I", "title": "Gas storage, the import balance and the nuclear decision",
     "objects": ("the daily storage fill and the entry-point flows",
                 "MAVIR's system load and import balance",
                 "declared nuclear outages",
                 "the Paks II milestones and the long-term supply contracts"),
     "conditions": ("the storage fill relative to its own seasonal norm",
                    "a declared nuclear outage in force against a full fleet",
                    "the heating-season phase, since a landlocked importer with storage faces a "
                    "STOCK decision and not only a flow one"),
     "instruments": ("XNGUSD", "GER40", "EUSTX50"),
     "controls": ("the European storage aggregate over the same days, separating 'Europe is "
                  "short' from 'Hungary is short'",
                  "matched days in seasons with a normal fill",
                  "the German day-ahead and gas prices as the dominant explanation"),
     "mechanism_family": "physical_supply", "horizon": "multi_day",
     "notes": "storage is large relative to demand here, which is why the fill level is a "
              "conditioning state and not a headline"},
    {"id": "HU-J", "title": "The AKK auction clock and the retail bond programme",
     "objects": ("the quarterly issuance calendar and the weekly auctions",
                 "the cut-off yield and the bid-to-cover",
                 "the holder structure's two opposing lines -- non-resident and household",
                 "the weekly retail sales run-rate"),
     "conditions": ("a bond auction Thursday against a bill auction Tuesday against neither",
                    "a bid-to-cover in the lower tail of its own trailing distribution",
                    "a rising household share against a rising non-resident share"),
     "instruments": ("EURHUF", "USDHUF", "EURPLN"),
     "controls": ("the matched non-auction weekday in the same week",
                  "Polish and Czech auction mornings, separating 'CEE supply' from 'Hungarian "
                  "supply'",
                  "weeks in which the calendar was published but no auction was held"),
     "mechanism_family": "calendar_settlement", "horizon": "session",
     "notes": "the Tuesday bill auction collides with the Tuesday rate decision, which is a "
              "collision the pack separates rather than pools"},
    {"id": "HU-K", "title": "The KSH release clock and the 08:30 local print",
     "objects": ("the CPI, industrial production, trade and GDP prints",
                 "the published release calendar a year ahead",
                 "the revision schedule",
                 "the German 08:00 CET releases half an hour later on the winter clock"),
     "conditions": ("the DST regime, which decides whether the Hungarian print is readable "
                    "BEFORE the German one or simultaneously with it",
                    "the release type: an inflation print with a published target against an "
                    "activity print with none",
                    "whether an administered price change lands in the same print"),
     "instruments": ("EURHUF", "USDHUF", "GER40"),
     "controls": ("matched non-release weekdays at the same LOCAL clock time",
                  "the German print at 08:00 CET as the competing explanation",
                  "EURPLN over the same window, since Polish prints land on a different clock"),
     "mechanism_family": "release_surprise", "horizon": "intraday",
     "notes": "the winter-clock ordering advantage is real and it DISAPPEARS in summer, which "
              "`release_minute_utc` is there to keep straight"},
    {"id": "HU-L", "title": "The decreed calendar: bridge rest days and working Saturdays",
     "objects": ("the eight statutory fixed days and the three Easter-derived ones",
                 "Nagypentek's arrival in 2017 as a new closed day",
                 "the decreed bridge rest days and the Saturdays worked to pay for them",
                 "the statutory days lost at the weekend with no substitute"),
     "conditions": ("a decreed rest day against a statutory holiday against an ordinary weekday",
                    "a WORKING SATURDAY, when Hungarian corporates and banks are at work and "
                    "every neighbouring market is shut",
                    "CET against CEST"),
     "instruments": ("EURHUF", "EUSTX50", "GER40"),
     "controls": ("matched weekdays 26 weeks away, the desk's standard holiday control",
                  "ordinary Saturdays, which are the only honest null for a working Saturday",
                  "German and Czech holidays over the same windows"),
     "mechanism_family": "holiday_liquidity", "horizon": "session",
     "notes": "the working Saturday is a genuinely unique liquidity state in the CEE calendar "
              "and it is DECLARED, never computed"},
    {"id": "HU-M", "title": "The MNB gold programme as a stepped official bid",
     "objects": ("the announced gold increases and their dates",
                 "the monthly tonnage series",
                 "the reserve headline the purchase is funded from",
                 "the political framing that makes the programme sticky"),
     "conditions": ("a month containing an announced step against an ordinary month",
                    "the size of the step relative to the existing stock",
                    "whether another CEE central bank announced in the same window"),
     "instruments": ("XAUUSD", "EURHUF"),
     "controls": ("the World Gold Council aggregate official-sector purchase series",
                  "the Czech gold programme, which ramps monthly rather than in steps: two "
                  "shapes, and only one of them can be the reason XAUUSD moved",
                  "matched months before the programme began"),
     "mechanism_family": "institutional_flow", "horizon": "multi_day",
     "notes": "the cross-pack test against cz is the interesting one and it is declared in "
              "INTERACTIONS rather than left implicit"},
)

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "hu_mnb_decision_windows", "domain_ids": ("HU-A",), "kind": "event",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.hu.miners:mnb_decision_windows",
     "needs": ("CENTRAL_BANK decision dates", "EURHUF, USDHUF, EURPLN H1 bars"),
     "notes": "split by the two-rate regime, because a decision about a rate that did not bind "
              "is not the same event as one about a rate that did"},
    {"name": "hu_two_rate_regime", "domain_ids": ("HU-B", "HU-C"), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.hu.miners:two_rate_regime",
     "needs": ("TWO_RATE_REGIME", "EURHUF, USDHUF, CHFHUF D1 bars"),
     "notes": "the two dated boundaries with the CEE peers as the concurrent null"},
    {"name": "hu_six_cross_panel", "domain_ids": ("HU-D",), "kind": "residual",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.hu.miners:six_cross_panel",
     "needs": ("EURHUF, USDHUF, AUDHUF, CHFHUF, GBPHUF, NZDHUF D1 bars",),
     "notes": "the pack's structural advantage: six simultaneous prices of one currency, so a "
              "common move can be told from a funding leg's own story"},
    {"name": "hu_auction_calendar", "domain_ids": ("HU-J",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.hu.miners:auction_calendar",
     "needs": ("the AKK Thursday bond clock", "EURHUF H1 bars"),
     "notes": "the matched non-auction weekday placebo is built in"},
    {"name": "hu_decreed_calendar", "domain_ids": ("HU-L", "HU-K"), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.hu.miners:decreed_calendar",
     "needs": ("SWAPPED_DAYS", "EURHUF, EUSTX50, GER40 H1 bars"),
     "notes": "bridge rest days and WORKING SATURDAYS as two different declared states"},
    {"name": "hu_transmission_seeds",
     "domain_ids": ("HU-E", "HU-F", "HU-G", "HU-H", "HU-I", "HU-M"), "kind": "transfer",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.hu.miners:transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED",),
     "notes": "the pack's map as HYPOTHESIS discoveries, deduplicated by the registry"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("HU-A", "HU-B"), "release_surprise": ("HU-K", "HU-G"),
    "calendar_settlement": ("HU-J", "HU-L"), "holiday_liquidity": ("HU-L",),
    "positioning": ("HU-D",), "carry_funding": ("HU-B", "HU-C"),
    "corporate_flow": ("HU-H", "HU-I"), "institutional_flow": ("HU-M", "HU-E"),
    "equity_mechanics": ("HU-L",), "derivatives_expiry": ("HU-L",),
    "failure": ("HU-F", "HU-H"), "residual": ("HU-D", "HU-B"),
    "transfer": ("HU-E", "HU-I"), "scouts": ("HU-G", "HU-E"),
    "session_microstructure": ("HU-L", "HU-K"),
}

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "HU-T1", "source": "The MNB monthly base-rate decision",
     "target": "EURHUF", "targets": ("EURHUF", "USDHUF"), "to_country": "hu", "sign": "-",
     "mechanism": "a rate surprise against a published 3% target repriced into the forint "
                  "within minutes, observable on SIX crosses at once so the forint factor can "
                  "be separated from the funding leg",
     "horizon": "intraday", "horizon_class": "intraday", "lag_days": 0.0,
     "actor": "the Monetaris Tanacs",
     "constraint": "the monthly calendar is not the full policy event list; the effective rate "
                   "was set daily outside it for eleven months",
     "flow": "rate repricing",
     "condition": "a meeting outside the two-rate regime, split by DST",
     "control": "the four nearest non-meeting Tuesdays at the same local clock; ECB days",
     "falsifier": "the decision window matches the matched Tuesday once EURUSD is controlled "
                  "for", "evidence": "HYPOTHESIS"},
    {"id": "HU-T2", "source": "The 18% one-day deposit tender above a 13% base rate",
     "target": "EURHUF", "targets": ("EURHUF", "USDHUF", "CHFHUF"), "to_country": "hu",
     "sign": "-",
     "mechanism": "for eleven months the real cost of funding a forint short was the TENDER "
                  "rate and not the base rate; every carry, differential and policy-surprise "
                  "series built on the base rate over that window measures a rate nobody could "
                  "fund at",
     "horizon": "the regime, with two dated boundaries", "horizon_class": "multi_day",
     "lag_days": 0.0, "actor": "the MNB money-market desk",
     "constraint": "the tender was decided DAILY, outside the published meeting calendar",
     "flow": "effective funding cost",
     "condition": "inside 2022-10-14..2023-09-26, conditioned on the tender-to-base spread",
     "control": "EURPLN and EURCZK over the identical windows; the same statistic computed on "
                "the base rate, which is the error being measured",
     "falsifier": "the tender rate adds nothing to the base rate in explaining the six crosses "
                  "over the window", "evidence": "MEASURED_ELSEWHERE"},
    {"id": "HU-T3", "source": "The common factor across the six broker-quoted HUF crosses",
     "target": "EURHUF", "targets": ("EURHUF", "USDHUF", "AUDHUF", "CHFHUF", "GBPHUF",
                                     "NZDHUF"),
     "to_country": "hu", "sign": "+",
     "mechanism": "six simultaneous prices of one currency against six different funding legs "
                  "decompose a move into the forint's own factor and each leg's story -- the "
                  "substitute for a COT report that does not exist for HUF",
     "horizon": "days to weeks", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the offshore forint carry account",
     "constraint": "the panel is only informative if the six crosses are quoted at the same "
                   "timestamps; a stale leg contaminates the factor",
     "flow": "position building and unwinding",
     "condition": "days when the first principal component explains an unusually large share",
     "control": "the funding legs alone (AUDNZD, EURUSD) which must explain the residual; "
                "EURPLN and EURCZK, which must move with a regional factor",
     "falsifier": "the common factor adds nothing to EURHUF alone, in which case the panel is "
                  "redundant", "evidence": "HYPOTHESIS"},
    {"id": "HU-T4", "source": "A Council suspension or Commission release of Hungarian EU funds",
     "target": "EURHUF", "targets": ("EURHUF", "EURCZK", "EURPLN"), "to_country": "hu",
     "sign": "-",
     "mechanism": "a dated, published, binary political decision with a large forced "
                  "EUR-to-HUF conversion behind a release and a political risk premium between "
                  "decisions",
     "horizon": "the decision day and the following week", "horizon_class": "multi_day",
     "lag_days": 1.0, "actor": "the European Commission and Council",
     "constraint": "the decision is often leaked or anticipated, so the test must use the "
                   "earliest public date and not the formal one",
     "flow": "forced conversion plus premium repricing",
     "condition": "a suspension against a release, sized by the tranche",
     "control": "EURCZK, the leg with no political discount, over the identical windows",
     "falsifier": "decision dates carry no EURHUF effect beyond EURCZK's own move",
     "evidence": "HYPOTHESIS"},
    {"id": "HU-T5", "source": "The 2015 conversion of household FX mortgages into forint",
     "target": "CHFHUF", "targets": ("CHFHUF", "EURHUF"), "to_country": "hu", "sign": "+",
     "mechanism": "before the conversion a CHF rally raised Hungarian mortgage payments "
                  "directly and fed back into the forint; the conversion cut that loop, so the "
                  "CHFHUF relationship before and after 2015 is not one relationship",
     "horizon": "a permanent structural break", "horizon_class": "multi_day", "lag_days": 0.0,
     "actor": "the MNB and the conversion acts",
     "constraint": "a single dated episode, so the test is distributional and not an event study",
     "flow": "balance-sheet channel removal",
     "condition": "episodes of CHF strength before 2015 against the same after",
     "control": "the Polish FX-mortgage stock, which was NOT converted and whose loop is still "
                "live: the difference is the mechanism",
     "falsifier": "CHFHUF's sensitivity to CHF strength is unchanged across 2015-02-01",
     "evidence": "MEASURED_ELSEWHERE"},
    {"id": "HU-T6", "source": "A gazetted change to the household utility price cap",
     "target": "EURHUF", "targets": ("EURHUF", "XNGUSD"), "to_country": "hu", "sign": "-",
     "mechanism": "an administered household energy price switched by decree; the 2022 "
                  "narrowing moved above-threshold consumption to the market price and produced "
                  "the largest Hungarian inflation step of the decade",
     "horizon": "the following CPI print", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the government as price-cap authority",
     "constraint": "the decree is usually leaked before it is gazetted, so the event date is "
                   "the leak and not the publication",
     "flow": "administered price into CPI",
     "condition": "a cap change whose gap to the market price is large",
     "control": "the non-regulated CPI components as an internal placebo; the Czech regulated "
                "step, which is set by methodology rather than decree",
     "falsifier": "CPI surprises after a cap change are uncorrelated with its size",
     "evidence": "HYPOTHESIS"},
    {"id": "HU-T7", "source": "The Druzhba pipeline-crude exemption and the refining spread",
     "target": "XBRUSD", "targets": ("XBRUSD", "XNGUSD"), "to_country": "global", "sign": "+",
     "mechanism": "Hungary's exemption from the EU seaborne crude ban leaves its refiner buying "
                  "pipeline crude at a discount European competitors cannot get; a pipeline "
                  "interruption or a sanctions decision removes it on a date",
     "horizon": "days to a quarter", "horizon_class": "multi_day", "lag_days": 2.0,
     "actor": "MOL as the exempt refiner",
     "constraint": "the DISCOUNT ITSELF is a LICENSED assessment and unreadable here, so the "
                   "claim is measured on the benchmark and the disclosed margin",
     "flow": "crude slate and refining spread",
     "condition": "a pipeline interruption or a sanctions decision in the window",
     "control": "the European refining margin over the same quarters; quarters with no event",
     "falsifier": "the Hungarian disclosed margin adds nothing to a Brent-based model of the "
                  "European margin", "evidence": "HYPOTHESIS"},
    {"id": "HU-T8", "source": "Hungarian gas storage fill against its seasonal norm",
     "target": "XNGUSD", "targets": ("XNGUSD", "GER40"), "to_country": "global", "sign": "-",
     "mechanism": "a landlocked importer with storage large relative to demand faces a STOCK "
                  "decision: a low fill entering the heating season converts into an urgent "
                  "import call, and a high one suppresses it",
     "horizon": "weeks", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "MVM and the storage operator",
     "constraint": "Hungary is small relative to the European gas market, so the claim must "
                   "beat the EUROPEAN storage aggregate to mean anything",
     "flow": "storage into import call",
     "condition": "a fill in the lower tail of its own seasonal distribution entering winter",
     "control": "the European storage aggregate; matched days in normal-fill seasons",
     "falsifier": "the Hungarian fill adds nothing to the European aggregate in explaining the "
                  "gas benchmark", "evidence": "HYPOTHESIS"},
    {"id": "HU-T9", "source": "The AKK Thursday bond auction",
     "target": "EURHUF", "targets": ("EURHUF", "USDHUF"), "to_country": "hu", "sign": "-",
     "mechanism": "a dated forced-supply event on a published quarterly calendar; the surprise "
                  "is entirely in the outcome -- the cut-off and the bid-to-cover against their "
                  "own trailing distribution",
     "horizon": "intraday to two days", "horizon_class": "session", "lag_days": 0.0,
     "actor": "AKK Zrt.",
     "constraint": "the Tuesday bill auction collides with the Tuesday rate decision, so the "
                   "two clocks must be separated rather than pooled",
     "flow": "primary supply",
     "condition": "a bid-to-cover in the lower tail of its trailing distribution",
     "control": "the matched non-auction weekday in the same week; Polish and Czech auction "
                "mornings",
     "falsifier": "auction mornings match the matched weekday across all six crosses",
     "evidence": "HYPOTHESIS"},
    {"id": "HU-T10", "source": "A Hungarian decreed rest day or working Saturday",
     "target": "EURHUF", "targets": ("EURHUF", "EUSTX50"), "to_country": "hu", "sign": "+",
     "mechanism": "a bridge rest day closes Budapest while the euro area trades, and a WORKING "
                  "SATURDAY puts Hungarian corporates and banks at work when every neighbouring "
                  "market is shut -- a liquidity state with no European counterpart at all",
     "horizon": "the session", "horizon_class": "session", "lag_days": 0.0,
     "actor": "the ministry that issues the work-schedule decree",
     "constraint": "NO RULE COMPUTES THESE; they are declared per year and 2026 is empty until "
                   "the decree is read",
     "flow": "liquidity withdrawal or addition",
     "condition": "a declared bridge rest day, or a declared working Saturday",
     "control": "matched weekdays 26 weeks away; ORDINARY Saturdays as the only honest null for "
                "a working Saturday",
     "falsifier": "declared days match their matched controls on every spread and range "
                  "measure", "evidence": "HYPOTHESIS"},
    {"id": "HU-T11", "source": "An announced MNB gold purchase step",
     "target": "XAUUSD", "targets": ("XAUUSD",), "to_country": "global", "sign": "+",
     "mechanism": "a disclosed, price-insensitive official buyer arriving in a handful of large "
                  "announced STEPS rather than as a smooth programme -- a different execution "
                  "shape from the Czech monthly ramp, and the two are separable",
     "horizon": "the announcement month", "horizon_class": "multi_day", "lag_days": 15.0,
     "actor": "the MNB reserve management",
     "constraint": "monthly disclosure only, so the flow is inferred rather than observed live",
     "flow": "official gold purchase",
     "condition": "a month containing an announced step",
     "control": "the World Gold Council aggregate official-sector series; the Czech programme's "
                "monthly ramp over the same months",
     "falsifier": "Hungarian announcement months show no XAUUSD effect beyond the aggregate "
                  "official-sector series", "evidence": "HYPOTHESIS"},
    {"id": "HU-T12", "source": "Hungarian industrial production and the vehicle and battery "
                               "lines",
     "target": "GER40", "targets": ("GER40", "EUSTX50"), "to_country": "de", "sign": "+",
     "mechanism": "Hungarian vehicle and battery plants are subcontracted capacity in the "
                  "German chain, and the battery line is the newest and most energy-intensive "
                  "part of it, so the Hungarian print carries both an industrial and an energy "
                  "signal",
     "horizon": "1 to 2 months", "horizon_class": "multi_day", "lag_days": 35.0,
     "actor": "the vehicle and battery plants and their German customers",
     "constraint": "the schedule is set abroad, so the claim must beat the German print",
     "flow": "order book into output",
     "condition": "months where the Hungarian print diverges from the German one",
     "control": "German industrial production as the dominant regressor; the Czech print over "
                "the same months, which is the same chain's other limb",
     "falsifier": "the Hungarian series adds nothing to a German-production-based forecast of "
                  "GER40", "evidence": "HYPOTHESIS"},
)

#: INTERACTION MINERS -- the other country packs this one has a MEASURABLE interaction with.
INTERACTIONS: tuple[dict[str, Any], ...] = (
    {"with": "cz",
     "mechanism": "the EU funds conditionality switch, with Czechia as the CLEAN CONTROL. One "
                  "paymaster, three member states, and a suspension pulled for Hungary and "
                  "never for Czechia -- so EURCZK is the CEE leg with no political discount in "
                  "it and is the null every Hungarian political event must beat. The two gold "
                  "programmes are the second interaction: a Hungarian stepped bid against a "
                  "Czech monthly ramp, and only one of them can be why XAUUSD moved",
     "observable": "the EURHUF/EURCZK spread around Council and Commission decision dates; the "
                   "two central banks' disclosed gold tonnage in the same months",
     "targets": ("EURHUF", "EURCZK", "XAUUSD"),
     "control": "Czech-specific events in the same windows, and the euro-area tape"},
    {"with": "pl",
     "mechanism": "the CEE convergence complex AND the FX-mortgage counterfactual. Poland did "
                  "NOT convert its household CHF mortgages, so the balance-sheet loop Hungary "
                  "cut in 2015 is still live there: the difference between the two countries' "
                  "sensitivity to Swiss franc strength IS the mechanism of HU-F. Poland also "
                  "faced its own conditionality suspension on a different timeline, which "
                  "separates 'EU politics' from 'Hungarian politics'",
     "observable": "EURHUF against EURPLN through CHF-strength episodes on either side of "
                   "2015-02-01; the two countries' conditionality dates, which do not coincide",
     "targets": ("EURHUF", "EURPLN", "CHFHUF"),
     "control": "EURUSD and the German industrial print, which both currencies are exposed to "
                "before either is exposed to the other"},
    {"with": "ea",
     "mechanism": "the German industrial chain and the ECB clock. Hungarian vehicle and battery "
                  "capacity is subcontracted German capacity, and the MNB decides on a monthly "
                  "Tuesday clock that repeatedly lands near an ECB decision -- so a Hungarian "
                  "decision-day effect that coincides with an ECB day is a euro event until "
                  "proven otherwise. The KSH 08:30 local print lands half an hour BEFORE the "
                  "08:00 CET German releases on the winter clock and simultaneously in summer, "
                  "which is a DST-dependent ordering the pack computes rather than assumes",
     "observable": "GER40 and EUSTX50 around Hungarian prints; the MNB-ECB differential; the "
                   "07:30 versus 08:00 UTC release ordering by season",
     "targets": ("GER40", "EUSTX50", "EURHUF"),
     "control": "ECB decision days and German release days as the competing explanation"},
    {"with": "ru",
     "mechanism": "the energy exception. Hungary kept a pipeline-crude exemption from the EU "
                  "import ban and a long-term gas relationship while its neighbours severed "
                  "theirs, and Paks II is financed and supplied under an intergovernmental "
                  "agreement -- so Hungarian refining margins, gas storage economics and the "
                  "nuclear build carry a Russian-supply term that Czech and Polish ones no "
                  "longer do",
     "observable": "the Hungarian disclosed refining margin against the European one through "
                   "sanctions and pipeline-interruption dates; the storage fill through supply "
                   "episodes",
     "targets": ("XBRUSD", "XNGUSD", "EURHUF"),
     "control": "the European refining margin and the European storage aggregate, plus the "
                "Czech and Polish energy positions, which have no exemption"},
    {"with": "uk",
     "mechanism": "the GBPHUF leg and the non-euro European rate complex. GBPHUF is one of only "
                  "a handful of sterling exotic crosses this broker quotes, so a Bank of "
                  "England decision reaches the forint panel directly -- and a move that "
                  "appears in GBPHUF but not in the other five crosses is a STERLING event "
                  "wearing a forint's hat, which is exactly the decomposition HU-D exists for",
     "observable": "the GBPHUF residual after the six-cross common factor is removed, around "
                   "BoE decision days and UK inflation prints",
     "targets": ("GBPHUF", "EURHUF", "EURUSD"),
     "control": "the other five HUF crosses over the identical windows, and EURUSD"},
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "the FX-mortgage overhang and orthodox policy", "start": "2010-01-01",
     "end": "2013-03-03",
     "regime": "a large household CHF-mortgage stock, an IMF programme repaid early in 2013, "
               "and a central bank whose rate decisions fed straight into household balance "
               "sheets through the currency",
     "markers": ("2011 the early-repayment scheme at fixed rates",
                 "2013 the IMF standby repaid ahead of schedule"),
     "why_it_matters": "the era in which the CHFHUF loop was live and dominant; every estimate "
                       "of the forint's sensitivity to the Swiss franc taken from here belongs "
                       "to a channel that no longer exists",
     "status": "SETTLED"},
    {"name": "the easing cycle and the Self-Financing Programme", "start": "2013-03-04",
     "end": "2015-01-31",
     "regime": "a new governor, a long easing cycle, and a programme designed to shift the "
               "funding of the state toward domestic holders and away from non-residents",
     "markers": ("2013-03 the leadership change",
                 "2014-11-07 the household FX-loan conversion announced"),
     "why_it_matters": "the structural shift in WHO holds Hungarian debt begins here, and it is "
                       "the long-run driver of the AKK holder table HU-J is built on",
     "status": "SETTLED"},
    {"name": "the post-conversion forint", "start": "2015-02-01", "end": "2020-03-31",
     "regime": "the household FX-loan stock converted at administratively fixed rates and the "
               "foreign currency supplied from reserves; rates driven to and held at record "
               "lows; the exchange became majority central-bank-owned",
     "markers": ("2015-02-01 the conversion takes effect",
                 "2015 the MNB acquires the Budapest Stock Exchange",
                 "2016-2019 the base rate at its record low"),
     "why_it_matters": "THE CHFHUF RELATIONSHIP CHANGES HERE and does not change back; a study "
                       "pooling 2010-2026 is pooling two different currencies",
     "status": "SETTLED"},
    {"name": "the pandemic and the one-week deposit detaching", "start": "2020-04-01",
     "end": "2022-10-13",
     "regime": "the one-week deposit rate became the effective instrument and moved away from "
               "the base rate; a hiking cycle from June 2021 that accelerated through 2022 as "
               "inflation became the highest in the EU and the forint made record lows",
     "markers": ("2020-04 the one-week deposit becomes the effective rate",
                 "2021-06-22 the first hike of the cycle",
                 "2022-09-27 the last base-rate hike at 13%"),
     "why_it_matters": "the FIRST detachment of the effective rate from the base rate, and the "
                       "rehearsal for the one that followed; a base-rate series here is already "
                       "not the funding cost",
     "status": "SETTLED"},
    {"name": "the two-rate emergency: an 18% one-day deposit", "start": "2022-10-14",
     "end": "2023-09-25",
     "regime": "an overnight deposit quick tender at 18% above a 13% base rate, decided daily "
               "outside the meeting calendar, alongside FX-market measures; the EU funds "
               "suspension ran in parallel and the two are entangled",
     "markers": ("2022-10-14 the tender introduced at 18%",
                 "2022-12 the Council decision suspending cohesion funds",
                 "2023-05 onward the monthly convergence steps begin"),
     "why_it_matters": "ANY Hungarian carry, differential or policy-surprise series built on "
                       "the BASE rate across this window is measuring a rate nobody could fund "
                       "at, by up to five percentage points; TWO_RATE_REGIME enumerates it",
     "status": "SETTLED"},
    {"name": "convergence and the easing cycle", "start": "2023-09-26", "end": "2024-12-31",
     "regime": "the one-day and base rates merged at 13% on 2023-09-26 and a conventional "
               "easing cycle followed through 2024; EU tranches began to be released against "
               "legislative milestones",
     "markers": ("2023-09-26 the instruments merged",
                 "2023-12 the first large tranche releases",
                 "2024 the monthly easing sequence"),
     "why_it_matters": "the boundary at which the Hungarian policy rate becomes a single number "
                       "again, which is where a pooled policy study may finally begin",
     "status": "SETTLED"},
    {"name": "the single-rate regime and the remaining conditionality", "start": "2025-01-01",
     "end": "2026-12-31",
     "regime": "one policy rate, a forint that still carries a political premium, a household "
               "bond programme that has changed who owns the debt, and an energy position that "
               "still rests on a revocable exemption",
     "markers": ("2025 the base rate as the sole instrument",
                 "the outstanding cohesion tranches still conditional"),
     "why_it_matters": "the current regime; the MNB's own decision calendar for it is NOT "
                       "carried in this pack and must be read before a 2026 cell is compiled",
     "status": "OPEN"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "SIX HUF crosses are quoted by this broker",
     "measured": "EURHUF, USDHUF, AUDHUF, CHFHUF, GBPHUF and NZDHUF are all in "
                 "data/universe/universe.json",
     "consequence": "this is the widest single-currency cross set the desk quotes, and it is "
                    "the reason HU-D can decompose a forint move rather than guess at it"},
    {"constraint": "no COT or exchange positioning series exists for HUF",
     "measured": "no forint future trades on any exchange the desk reads",
     "consequence": "positioning is the AKK monthly holder table plus the six-cross common "
                    "factor; the EUR COT leg is never used as a proxy"},
    {"constraint": "the effective policy rate was NOT the base rate for eleven months",
     "measured": "TWO_RATE_REGIME: 18% one-day deposit against a 13% base rate, 2022-10-14 to "
                 "2023-09-26",
     "consequence": "every carry, differential and surprise series must be recomputed on the "
                    "tender rate inside that window, and a pooled series is simply wrong"},
    {"constraint": "the MNB decision calendar for 2025-2026 is not carried here",
     "measured": "CENTRAL_BANK['decision_dates'] stops in 2024 and dates_status says so",
     "consequence": "HU-A cells for 2025 and 2026 are UNMEASURED until the published calendar "
                    "is read; the pack refuses to invent a decision date (L1.28a)"},
    {"constraint": "the work-schedule decree for 2026 has not been read",
     "measured": "SWAPPED_DAYS[2026] is empty and SWAPPED_DAYS_STATUS says NOT_DECLARED",
     "consequence": "no 2026 bridge rest day or working Saturday is invented; an HU-L cell for "
                    "2026 is UNMEASURED rather than assumed"},
    {"constraint": "the Urals-to-Brent discount and the Central European gas assessments forbid "
                   "machine extraction",
     "measured": "Argus, ICIS and Platts terms; registered machine_use_allowed=false",
     "consequence": "HU-H is measured on the executable crude benchmark and the refiner's own "
                    "disclosed margin, never on a licensed assessment"},
    {"constraint": "no BUX CFD exists and the index is four names",
     "measured": "the broker registry holds no BUX symbol; OTP, MOL, Richter and Magyar Telekom "
                 "are most of the index",
     "consequence": "HU-L is a MECHANICS domain about the calendar and the settlement clock; a "
                    "BUX study would be a single-name study and the two-lane order forbids it"},
    {"constraint": "the retail bond rate page and the MEKH tariff pages overwrite in place",
     "measured": "both show today's number and keep no vintage",
     "consequence": "the point-in-time history of the household savings choice and of the price "
                    "cap exists only in the archive layer's crawls"},
)
INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "AKK monthly holder structure: the non-resident and household shares",
    "AKK and Allamkincstar weekly retail government securities sales",
    "MNB monthly reserves, gold tonnage and swap book",
    "MNB weekly one-day and one-week deposit stock",
    "BET monthly foreign turnover share",
    "European Commission RRF and cohesion payment decisions for Hungary")
SERIES: dict[str, str] = {
    "HU_POLICY": "MNB:alapkamat", "HU_EFFECTIVE": "MNB:egynapos_betet",
    "HU_FX_FIXING": "MNB:arfolyam_EURHUF", "HU_RESERVES": "MNB:reserves",
    "HU_GOLD": "MNB:gold_tonnes", "HU_BUBOR": "MNB:BUBOR_3M",
    "HU_CPI": "KSH:CPI", "HU_IP": "KSH:industrial_production",
    "HU_GDP": "KSH:GDP_flash", "HU_AUCTION": "AKK:auction_yield",
    "HU_NONRESIDENT": "AKK:nonresident_share", "HU_RETAIL_BOND": "AKK:retail_sales",
    "HU_STORAGE": "FGSZ:storage_fill", "HU_LOAD": "MAVIR:system_load",
    "HU_CAP": "MEKH:capped_tariff",
}


# --------------------------------------------------------------------------- mechanism fns
def in_two_rate_regime(day: date) -> bool:
    """True when a date sits inside the 18%-one-day-deposit regime.

    THE POINT OF THIS FUNCTION. Inside this window the Hungarian policy rate was two numbers
    and the one that mattered for funding was the higher one, so any carry, differential or
    policy-surprise series computed on the base rate here is measuring a rate nobody could fund
    at. The mask is inclusive of the introduction day and exclusive of the merger day, which is
    itself the regime-break event.
    """
    return bool(TWO_RATE_REGIME["introduced"] <= day < TWO_RATE_REGIME["converged"])


def two_rate_days(start: date, end: date) -> list[date]:
    """Every WEEKDAY inside the two-rate regime that also falls inside [start, end]."""
    lo = max(start, TWO_RATE_REGIME["introduced"])
    hi = min(end, TWO_RATE_REGIME["converged"])
    out: list[date] = []
    cur = lo
    while cur < hi:
        if cur.weekday() < 5:
            out.append(cur)
        cur += timedelta(days=1)
    return out


def post_conversion(day: date) -> bool:
    """True when a date sits AFTER the 2015 household FX-loan conversion took effect.

    CHFHUF before and after this boundary are not the same relationship: the conversion removed
    the household balance-sheet loop through which a Swiss franc rally used to reach the forint.
    """
    return bool(day >= FX_LOAN_CONVERSION["effective"])


def six_cross_panel() -> tuple[str, ...]:
    """The six broker-quoted HUF crosses, in a fixed order, as the panel HU-D decomposes.

    A COMMON move across all six is the forint; a move in one is that leg's own story. This is
    the substitute for a COT report that does not exist for this currency, and it is a better
    one: six simultaneous prices rather than one weekly survey.
    """
    return tuple(s for s in EXECUTABLE_INSTRUMENTS if s.endswith("HUF"))


# --------------------------------------------------------------------------- cells
def cells() -> tuple[dict[str, Any], ...]:
    """THE TESTABLE CELLS THIS PACK MINTS: domain x executable instrument x named condition.

    The conditions are the DOMAIN's own declared conditions and the instruments are the
    DOMAIN's own declared instruments, never a cartesian product across the whole symbol list:
    a cell must name something this pack's data plane can actually evaluate.
    """
    rows: list[dict[str, Any]] = []
    execs = set(EXECUTABLE_INSTRUMENTS)
    for dom in DOMAINS:
        did = str(dom["id"])
        family = str(dom.get("mechanism_family") or "residual")
        horizon = str(dom.get("horizon") or "multi_day")
        control = " | ".join(str(c) for c in dom["controls"])
        for sym in dom["instruments"]:
            if sym not in execs:
                continue
            for i, cond in enumerate(dom["conditions"], start=1):
                rows.append({
                    "cell_id": f"HU:{did}:{sym}:C{i}",
                    "domain": did, "symbol": str(sym), "condition": str(cond),
                    "mechanism_family": family, "horizon": horizon, "control": control,
                    "why": f"{dom['title']} -- {cond}",
                })
    return tuple(rows)


CELLS: tuple[dict[str, Any], ...] = cells()

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
        "custom_miners": CUSTOM_MINERS, "miner_domains": MINER_DOMAINS,
        "transmission_edges_seed": TRANSMISSION_EDGES_SEED, "policy_eras": POLICY_ERAS,
        "transmission_targets": TRANSMISSION_TARGETS, "access_constraints": ACCESS_CONSTRAINTS,
        "region_desk": REGION_DESK, "forest": FOREST, "cot_currency": COT_CURRENCY,
        "export_economy": EXPORT_ECONOMY, "retail_leverage_regime": RETAIL_LEVERAGE_REGIME,
        "institutional_flow_sources": INSTITUTIONAL_FLOW_SOURCES, "series": SERIES,
        "mission": MISSION, "two_rate_regime": TWO_RATE_REGIME,
        "fx_loan_conversion": FX_LOAN_CONVERSION, "swapped_days": SWAPPED_DAYS,
        "interactions": INTERACTIONS, "cells": CELLS,
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
            "fixed_md": tuple(f"{m:02d}-{d:02d}" for m, d, _ in FIXED_NATIONAL),
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


# --------------------------------------------------------------------------- the department
def mine(ctx: Any = None) -> dict[str, Any]:
    """THE DEPARTMENT ENTRY. Pure Python, no network, no LLM, no heavy import.

    It reads the pack's own data plane and emits one row per transmission edge and one row per
    interaction through the department Ctx when one is given, and returns a plain report
    otherwise. Everything it cannot evaluate from the pack's own tables is listed by name in
    `unmeasured` rather than left out (L1.28a).
    """
    rows: list[dict[str, Any]] = []
    for e in TRANSMISSION_EDGES_SEED:
        rows.append({"kind": "transmission_edge", "code": CODE.lower(), "id": str(e["id"]),
                     "mechanism": str(e["mechanism"]), "targets": tuple(e["targets"]),
                     "evidence": str(e["evidence"]), "control": str(e["control"]),
                     "falsifier": str(e["falsifier"])})
    for row in INTERACTIONS:
        rows.append({"kind": "interaction", "code": CODE.lower(), "with": str(row["with"]),
                     "mechanism": str(row["mechanism"]), "targets": tuple(row["targets"]),
                     "observable": str(row["observable"]), "control": str(row["control"])})
    unmeasured = [
        "MNB decision calendar for 2025-2026: not published in this pack "
        "(CENTRAL_BANK.dates_status)",
        "the 2026 work-schedule decree: SWAPPED_DAYS[2026] is empty by design, so no bridge "
        "rest day or working Saturday is invented for that year",
        "HUF positioning: no COT or exchange series exists; the AKK holder table and the "
        "six-cross common factor are the substitutes",
        "the Urals-to-Brent discount and the Central European gas assessments are LICENSED and "
        "registered machine_use_allowed=false",
        "the intermediate one-day deposit convergence steps are PRESS_REPORTED and must be "
        "cited from the MNB before a cell is compiled on any of them",
    ]
    emitted = 0
    if ctx is not None:
        record = getattr(ctx, "record", None)
        note = getattr(ctx, "note", None)
        for row in rows:
            if callable(record):
                try:
                    record(**{"mechanism": f"hu_pack:{row.get('id') or row.get('with')}",
                              "payload": row})
                except TypeError:
                    record(row)
                emitted += 1
        if callable(note):
            for why in unmeasured:
                note("hu_pack:unmeasured", why)
    return {"code": CODE.lower(), "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "emitted": emitted, "rows": rows, "unmeasured": unmeasured,
            "cells_emitted": len(CELLS), "datasets": len(DATASETS), "actors": len(ACTORS),
            "domains": len(DOMAINS), "edges": len(TRANSMISSION_EDGES_SEED),
            "interactions": len(INTERACTIONS), "sources": len(SOURCE_CLASSES),
            "crosses": list(six_cross_panel()),
            "layers_covered": source_layer_coverage()["n_layers_covered"]}

