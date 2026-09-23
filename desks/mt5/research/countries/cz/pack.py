"""CZECHIA -- the floor, the hedged reserves and the German limb, as DATA.

See `countries/cz/__init__.py` for why this country earns its own department. This module is the
pack itself: identity, conventions, calendars, actors, domains, sources, datasets, edges, eras,
cells and the department entry `mine()`. Nothing here is prose for a human to act on; everything
here is read by a miner or checked by a test.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

# --------------------------------------------------------------------------- identity
CODE = "CZ"
NAME = "Czechia"
#: THE PARITY FENCE COUNTS THIS. One jurisdiction, declared rather than inferred from the
#: directory name, because a fence that infers is a fence that is wrong the day a pack grows.
JURISDICTIONS: tuple[str, ...] = ("cz",)
REGION_COMMAND = "europe"
REGION_DESK = "CEE"
FOREST = "europe"
CURRENCY = "CZK"
FISCAL_YEAR_END = "12-31"          # the state budget runs on the calendar year
NATIVE_LANGUAGES: tuple[str, ...] = ("cs", "sk", "de", "en")
COT_CURRENCY = ""                  # no CFTC contract exists for the koruna
EXPORT_ECONOMY = "manufacturing_exporter"      # vehicles and machinery into the German chain
RETAIL_LEVERAGE_REGIME = "esma_capped"         # an EU member state: ESMA 30:1 major-FX cap
MISSION = ("mine Czechia as the floor-and-exit economy it is: the CNB's 2013-2017 EUR/CZK 27.00 "
           "commitment and the truncated distribution it leaves behind, the reserve pile that "
           "paid for it and the equity and gold tranches that now hedge it, the fixed-time "
           "14:30 CET decision, the German automotive chain arriving as an INDEX transmission, "
           "the OTE day-ahead coupling and the CEPS cross-border flow into gas and aluminium, "
           "the MF CR auction calendar and the CSU release clock -- with EURCZK and USDCZK "
           "directly executable, which makes almost every mechanism here a fillable cell")

#: The instruments this pack may compile a cell against. Every one is in the broker registry and
#: none is a single-name equity. The PX index, the state bonds, PRIBOR and the day-ahead power
#: price are absent and live in TRANSMISSION_TARGETS.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "EURCZK", "USDCZK",                        # the koruna itself: directly quoted, both legs
    "EURUSD",                                  # the leg that separates a koruna move from a euro
    "EURPLN", "EURHUF",                        # the CEE convergence complex, the peer control
    "GER40", "EUSTX50", "FRA40", "NETH25",     # the German chain and the euro-area industrial tape
    "XNGUSD",                                  # the marginal Czech power plant's fuel
    "XALUSD",                                  # the smelter leg of an industrial power price
    "XAUUSD",                                  # the CNB's declared gold accumulation programme
    "US500",                                   # the reserve equity tranche's largest single market
)

#: EVERY INSTRUMENT THIS COUNTRY'S MECHANISMS RUN THROUGH THAT THE BROKER DOES NOT QUOTE, named
#: with what carries it instead. An absent instrument is a transmission hypothesis here, never a
#: silent hole and never a cell that can never be filled (L1.49).
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "PX (the Prague Stock Exchange index) and PX-TR",
     "venue": "Burza cennych papiru Praha (BCPP/PSE), owned by the Vienna exchange group",
     "why": "no CFD is quoted; the index is bank- and utility-heavy (Erste, KB, Moneta, CEZ) "
            "and its European parents carry the executable leg, which is also why a PX study "
            "would be a single-name study wearing an index's hat",
     "proxies": ("EUSTX50", "GER40", "EURCZK")},
    {"name": "Czech state bonds (statni dluhopisy) and the CZK swap curve",
     "venue": "MF CR primary auctions; the interbank secondary market",
     "why": "the rate path the CNB's decision actually moves; absent from the broker, so the "
            "decision is read on EURCZK and USDCZK and controlled with EURUSD",
     "proxies": ("EURCZK", "USDCZK", "EURPLN")},
    {"name": "PRIBOR (the Czech interbank reference rate) and the 2W repo rate",
     "venue": "Czech Financial Benchmark Facility; the CNB's repo tender",
     "why": "the policy instrument and its market echo; the carry a koruna position earns is "
            "PRIBOR minus EURIBOR, and that spread is the state CZ-D conditions on",
     "proxies": ("EURCZK", "EURPLN", "EURHUF")},
    {"name": "The OTE day-ahead electricity price for the Czech bidding zone",
     "venue": "OTE a.s., coupled to DE/AT/PL/SK/HU through SDAC at a 12:00 CET gate",
     "why": "power is not quoted by this broker; the Czech marginal plant burns lignite or gas, "
            "so the fuel leg is executable and the smelter's input cost is executable, while "
            "the price itself is an input series",
     "proxies": ("XNGUSD", "XALUSD", "GER40")},
    {"name": "EUA (EU emission allowance) futures",
     "venue": "EEX / ICE Endex",
     "why": "the carbon cost is half the Czech lignite plant's marginal cost and therefore half "
            "the transmission from a power price to an industrial one; not quoted here",
     "proxies": ("XNGUSD", "XALUSD", "GER40")},
    {"name": "Czech retail deposit and mortgage rates, and the refixation stock",
     "venue": "the commercial banks; the CNB's ARAD statistics",
     "why": "the household transmission channel arrives three to five years late through the "
            "refixation wave, which is why a Czech tightening cycle looks weak on impact and "
            "strong two years later; no instrument exists, the series conditions the eras",
     "proxies": ("EURCZK", "EUSTX50")},
    {"name": "The CNB's reserve portfolio itself (the equity tranche and the gold tranche)",
     "venue": "the CNB's own balance sheet, disclosed in the annual report and ARAD",
     "why": "a central bank whose reserves hold global equities rebalances into the world "
            "equity tape; the flow is institutional, dated by disclosure and executable only "
            "through the indices and gold it is invested in",
     "proxies": ("US500", "EUSTX50", "XAUUSD")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Ceska narodni banka -- bankovni rada CNB",
    "short": "CNB",
    "framework": "inflation_targeting",
    "committee": "the bankovni rada: the Governor, two Deputy Governors and four other members, "
                 "all appointed by the President of the Republic; seven votes, and the vote "
                 "split is published with the decision",
    "policy_instrument": "the two-week repo rate (2T repo sazba), inside a corridor whose floor "
                         "is the discount rate and whose ceiling is the Lombard rate; the "
                         "EXCHANGE RATE was used as the instrument from 2013-11-07 to "
                         "2017-04-06, when the 2W repo was at its technical zero",
    "mandate": "price stability under Act 6/1993 Sb.; the inflation target has been 2% with a "
               "+/-1pp tolerance band since 2010-01, which is why a Czech 'surprise' CAN be "
               "measured against a published number -- unlike most packs on this desk",
    "decision_rule": "EIGHT scheduled monetary-policy meetings a year; the decision is announced "
                     "at a FIXED 14:30 local time and the Governor's press conference follows at "
                     "about 15:45 local, so the announcement minute is a constant and not a "
                     "thing to be inferred",
    "decision_calendar_rule": "eight meetings a year, published a year in advance at cnb.cz; "
                              "four of them carry a new Monetary Policy Report and four do not, "
                              "and the two classes are NOT exchangeable -- a forecast-round "
                              "meeting carries a revised projection and an off-round one does "
                              "not, which is a conditioning state CZ-A keeps",
    "decision_dates": (
        "2013-11-07", "2017-04-06",
        "2021-06-23", "2021-08-05", "2021-09-30", "2021-11-04", "2021-12-22",
        "2022-02-03", "2022-03-31", "2022-05-05", "2022-06-22",
        "2023-12-21",
        "2024-02-08", "2024-03-20", "2024-05-02", "2024-06-27", "2024-08-01", "2024-09-25",
        "2024-11-07", "2024-12-19",
        "2025-02-06", "2025-05-07"),
    "dates_status": "PRESS_REPORTED AND PARTIAL, deliberately. The two 2013/2017 rows are the "
                    "floor's extraordinary meetings; the 2021-2022 rows are the hiking cycle; "
                    "the 2023-12-21 row is the first cut; the 2024 rows are the easing cycle. "
                    "RE-VERIFY every one against the cnb.cz decision archive before a cell is "
                    "compiled on it. The remainder of 2025 and the whole of 2026 are NOT "
                    "LISTED: the CNB publishes the calendar and this pack refuses to invent it "
                    "(L1.28a)",
    "decision_time_utc": "13:30",
    "announce_local": "14:30 Europe/Prague on the meeting day (13:30 UTC in CET, 12:30 UTC in "
                      "CEST); the press conference at about 15:45 local",
    "dst_rule": "Europe/Prague is CET (UTC+1) and CEST (UTC+2) on the EU rule -- last Sunday of "
                "March to last Sunday of October -- so the SAME 14:30 local decision lands at "
                "two different UTC minutes across the year and a pooled intraday window is two "
                "windows",
    "minutes_lag_days": 8,
    "publication_classes": ("menove_rozhodnuti", "zaznam_z_jednani_bankovni_rady",
                            "zprava_o_menove_politice", "zprava_o_financni_stabilite",
                            "devizove_rezervy", "kurzy_devizoveho_trhu", "ARAD_casove_rady"),
    "policy_rate_series": "CNB:2T_repo_sazba",
    "expected_rate_series": "CNB:FRA_3x6_implied",
    "consensus_proxy": "the FRA 3x6 and the PRIBOR curve on the morning of the meeting, plus the "
                       "published forecast path in the Monetary Policy Report -- the CNB is one "
                       "of the few central banks that publishes its OWN interest-rate "
                       "trajectory, so the surprise can be measured against the bank's own path",
    "consensus_proxy_trap": "the published CNB path is a FORECAST and not a commitment, and the "
                            "board has voted against it repeatedly; a 'surprise' measured "
                            "against the path measures the board's disagreement with its own "
                            "staff, which is a different object from a market surprise",
    "reserves_clock": "devizove rezervy are published monthly, about seven business days after "
                      "the month end, with the currency and instrument composition in the "
                      "annual report; the floor era's accumulation is visible as a step",
    "programme": "none: Czechia is an EU member state outside the euro area with no IMF "
                 "programme and no ERM II membership, so there is no external conditionality "
                 "clock here at all -- which is precisely what makes the floor a PURE domestic "
                 "policy experiment",
    "off_cycle": ("2013-11-07 the FX floor at 27.00 CZK/EUR announced at an extraordinary "
                  "meeting", "2017-04-06 the floor abandoned at an extraordinary meeting",
                  "2020-03-16 and 2020-03-26 emergency cuts to 1.00% and then 0.25%"),
    "root": "https://www.cnb.cz",
}
#: THE FLOOR, as three numbers a test can check. The CNB committed to intervene without limit to
#: keep EUR/CZK at or above 27.00; it did not defend a ceiling, so the distribution was truncated
#: on ONE side only, which is the fact every volatility and option statistic in that era depends
#: on and which a pooled sample destroys.
FLOOR_REGIME: dict[str, Any] = {
    "level_czk_per_eur": 27.00,
    "announced": date(2013, 11, 7),
    "exited": date(2017, 4, 6),
    "side": "one-sided: a FLOOR under EUR/CZK (a ceiling on the koruna), never a band",
    "commitment": "unlimited intervention in the FX market, declared publicly and repeated at "
                  "every meeting until the exit",
    "status": "SETTLED -- the two dates are public and undisputed; the intervention VOLUMES are "
              "published in the balance of payments and the reserve series",
    "what_it_invalidates": (
        "any EURCZK realised-volatility, option-implied or tail estimate that spans 2013-11-07 "
        "to 2017-04-06, because the downside of the distribution was administratively removed",
        "any carry or momentum backtest on EURCZK across the boundary: the carry was a "
        "one-sided free option and the momentum was a policy commitment",
        "any correlation of EURCZK with EURPLN or EURHUF inside the era, which measures the "
        "CNB's balance sheet and not a CEE factor",
        "any 'CEE beta' estimated on a window containing 2017-04-06, where a single scheduled "
        "day carries the whole regime change"),
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "CNB kurzy devizoveho trhu (the official daily koruna rate)",
     "local": "declared each working day after 14:30 Europe/Prague and valid for that day",
     "time_utc": "13:30", "time_utc_dst": "12:30",
     "dst_rule": "CET/CEST on the EU rule", "instruments": ("EURCZK", "USDCZK"),
     "window_minutes": 30,
     "why": "the rate the tax authority, the customs and every Czech accounting entry use; it "
            "is declared at the same minute as a policy decision on decision days, which is a "
            "collision a study must separate rather than average"},
    {"name": "PRIBOR fixing (the Czech interbank reference rate)",
     "local": "11:00 Europe/Prague, administered by the Czech Financial Benchmark Facility",
     "time_utc": "10:00", "time_utc_dst": "09:00", "dst_rule": "CET/CEST",
     "instruments": ("EURCZK", "EURPLN"), "window_minutes": 30,
     "why": "the carry leg of every koruna position and the rate Czech floating debt reprices "
            "on; absent from the broker, so it is a state variable and not a target"},
    {"name": "OTE / SDAC day-ahead auction gate closure",
     "local": "12:00 Europe/Prague, results published around 12:55",
     "time_utc": "11:00", "time_utc_dst": "10:00", "dst_rule": "CET/CEST",
     "instruments": ("XNGUSD", "XALUSD", "GER40"), "window_minutes": 60,
     "why": "one coupled auction sets the Czech, German, Austrian, Polish, Slovak and Hungarian "
            "day-ahead price at once; the gate minute is the only moment the whole Central "
            "European power complex clears simultaneously"},
    {"name": "Burza cennych papiru Praha closing auction (the PX close)",
     "local": "16:20-16:25 Europe/Prague", "time_utc": "15:20", "time_utc_dst": "14:20",
     "dst_rule": "CET/CEST", "instruments": ("EUSTX50", "GER40"), "window_minutes": 15,
     "why": "the domestic close; no PX CFD exists, so the European parents' indices carry it"},
    {"name": "ECB euro foreign exchange reference rates (the EUR/CZK concertation)",
     "local": "concertation at 14:15 Europe/Frankfurt, published about 16:00",
     "time_utc": "15:00", "time_utc_dst": "14:00", "dst_rule": "CET/CEST",
     "instruments": ("EURCZK", "EURPLN", "EURHUF"), "window_minutes": 30,
     "why": "the second official EUR/CZK print of the day and the one European accounts mark "
            "against; the gap between it and the CNB's 14:30 declaration is a measurable "
            "administered-price spread"},
    {"name": "LBMA gold price PM auction (the CNB gold programme's reference)",
     "local": "15:00 Europe/London", "time_utc": "15:00", "time_utc_dst": "14:00",
     "dst_rule": "GMT/BST", "instruments": ("XAUUSD",), "window_minutes": 15,
     "why": "the CNB declared a gold accumulation programme in 2024; the purchases are reported "
            "monthly and the reference they are marked at is this auction"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "CNB two-week repo tender", "kind": "weekday", "weekday": 2, "roll": "next",
     "window_utc": ("08:00", "11:00"), "instruments": ("EURCZK",),
     "why": "the regular 2W repo tender is the operational instrument between meetings; it is "
            "announced on the CNB's own tender calendar and the ALLOTMENT is the stance"},
    {"name": "MF CR primary auction of Czech state bonds", "kind": "weekday", "weekday": 2,
     "roll": "next", "window_utc": ("09:00", "13:00"), "instruments": ("EURCZK", "USDCZK"),
     "why": "the Ministry of Finance auctions medium and long bonds on a published quarterly "
            "calendar, most often midweek; the cut-off yield is the domestic rate path and the "
            "non-resident bid is the foreign flow into the koruna"},
    {"name": "Prague Stock Exchange T+2 settlement at the CDCP", "kind": "month_end",
     "roll": "previous", "window_utc": ("14:00", "15:30"), "instruments": ("EUSTX50", "GER40"),
     "why": "the Central Securities Depository settles T+2; the index reviews and the dividend "
            "season cluster at the month boundary"},
    {"name": "Month-end exporter hedging flow (the corporate forward book)", "kind": "month_end",
     "roll": "previous", "window_utc": ("07:00", "14:00"),
     "instruments": ("EURCZK", "USDCZK", "GER40"),
     "why": "Czech exporters invoice in EUR and hedge forward; the roll and the new-month "
            "hedging clusters into the last and first business days, which is the one recurring "
            "CZK flow that is not a policy decision"},
    {"name": "Quarter-end EU cohesion and RRF disbursement conversion", "kind": "quarter_end",
     "roll": "previous", "window_utc": ("08:00", "14:00"), "instruments": ("EURCZK", "EURPLN"),
     "why": "EU transfers arrive in EUR and are converted into CZK by the state; the schedule "
            "is set in Brussels and clusters at quarter boundaries, so it is a FORCED flow with "
            "a published calendar"},
    {"name": "Fiscal year end (31 December) and the state budget act", "kind": "fiscal_year_end",
     "roll": "previous", "window_utc": ("08:00", "16:00"), "instruments": ("EURCZK", "EUSTX50"),
     "why": "the budget year is the calendar year; the funding programme, the regulated energy "
            "prices and the excise schedule are all dated to it"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Burza cennych papiru Praha (PSE) -- PX, PX-TR, PX-GLOB",
     "index_symbols": (),
     "open_local": "09:00 (pre-open from 08:00)", "close_local": "16:25",
     "open_utc": "08:00", "close_utc": "15:25",
     "dst_rule": "CET/CEST on the EU rule, so the UTC session moves an hour twice a year",
     "auction": "opening call 08:00-09:00, continuous trading, closing call 16:20-16:25",
     "expiry_rule": "the listed derivatives market is effectively dormant; there is no monthly "
                    "index expiry clock to mine, which is itself a measurement",
     "holidays": "the statutory Czech calendar, including Good Friday since 2016",
     "notes": "NO CFD IS QUOTED on the PX, so the index enters only as a transmission target. "
              "The free float is small and bank- and utility-dominated, so a PX study is a "
              "single-name study wearing an index's hat -- the two-lane order forbids it and "
              "the European parents carry the executable leg instead"},
    {"name": "OTE a.s. -- the Czech electricity and gas market operator",
     "index_symbols": (), "open_local": "00:00", "close_local": "12:00",
     "open_utc": "23:00", "close_utc": "11:00", "dst_rule": "CET/CEST",
     "auction": "the day-ahead auction gate closes at 12:00 local and clears coupled with the "
                "German, Austrian, Polish, Slovak and Hungarian zones through SDAC",
     "expiry_rule": "hourly delivery products; the intraday market runs continuously after the "
                    "day-ahead clears",
     "holidays": "the market runs every calendar day; the HOLIDAY is a demand state, not a "
                 "closure -- a public holiday flattens industrial load and moves the marginal "
                 "plant down the merit order",
     "notes": "the day-ahead price is the input series of CZ-F; it is not quoted by the broker "
              "and its fuel and smelter legs are"},
    {"name": "The interbank CZK market and the CNB's FX operations",
     "index_symbols": (), "open_local": "08:00", "close_local": "17:00",
     "open_utc": "07:00", "close_utc": "16:00", "dst_rule": "CET/CEST",
     "auction": "no auction: the CNB intervenes directly and discloses the volumes with a lag "
                "in the balance of payments and the reserve series",
     "expiry_rule": "OTC forwards and options; the exporter book rolls at month ends",
     "holidays": "the Czech banking calendar",
     "notes": "deep enough to be directly executable at this broker, which is what separates "
              "this pack from most of the desk's emerging-market packs"},
)

SESSION_WINDOWS: tuple[dict[str, Any], ...] = (
    {"name": "cz_cnb_decision_cet", "start_utc": "13:00", "end_utc": "15:30",
     "notes": "the 14:30 local decision and the 15:45 local press conference in CET (winter)"},
    {"name": "cz_cnb_decision_cest", "start_utc": "12:00", "end_utc": "14:30",
     "notes": "the SAME local minutes in CEST (summer); a pooled intraday window is two "
              "windows, and this pack declares both rather than averaging them"},
    {"name": "cz_pse_session_cet", "start_utc": "08:00", "end_utc": "15:25",
     "notes": "the Prague continuous session plus its closing call, winter clock"},
    {"name": "cz_pse_session_cest", "start_utc": "07:00", "end_utc": "14:25",
     "notes": "the same local session, summer clock"},
    {"name": "cz_ote_gate", "start_utc": "11:00", "end_utc": "12:00",
     "notes": "the 12:00 CET day-ahead gate closure and the coupled clearing that follows"},
    {"name": "cz_german_morning_prints", "start_utc": "07:00", "end_utc": "08:00",
     "notes": "the 08:00 CET German industrial production, orders and trade releases -- the "
              "single most important foreign clock for Czech industry, and the control window "
              "every CZ-E claim must be measured against"},
)

RELEASE_CLASSES: tuple[dict[str, Any], ...] = (
    {"name": "CNB monetary policy decision (menove rozhodnuti)", "cadence": "8 per year",
     "time_utc": "13:30", "source": "Ceska narodni banka",
     "actual_series": "CNB:2T_repo_sazba", "expected_series": "CNB:FRA_3x6_implied",
     "notes": "a FIXED announcement minute, which is rare on this desk; four of the eight "
              "meetings carry a new Monetary Policy Report and four do not"},
    {"name": "CNB minutes and vote split (zaznam z jednani bankovni rady)",
     "cadence": "8 per year", "time_utc": "13:00", "source": "Ceska narodni banka",
     "actual_series": "CNB:vote_split", "expected_series": "UNMEASURED",
     "notes": "published eight days after the meeting; the vote split is the dispersion measure "
              "a single policy rate cannot carry"},
    {"name": "CNB declared exchange rates (kurzy devizoveho trhu)", "cadence": "daily",
     "time_utc": "13:30", "source": "Ceska narodni banka", "actual_series": "CNB:kurz_EURCZK",
     "expected_series": "n/a",
     "notes": "every working day; the machine-readable daily file is one of the cleanest "
              "official endpoints in the whole pack"},
    {"name": "CSU consumer price index (index spotrebitelskych cen)", "cadence": "monthly",
     "time_utc": "08:00", "source": "Cesky statisticky urad", "actual_series": "CZSO:CPI",
     "expected_series": "UNMEASURED",
     "notes": "09:00 local around the 10th-12th for the prior month; the regulated-energy line "
              "carries the ERU decision and is the CZ-M object"},
    {"name": "CSU industrial production and new orders (prumyslova produkce)",
     "cadence": "monthly", "time_utc": "08:00", "source": "Cesky statisticky urad",
     "actual_series": "CZSO:industrial_production", "expected_series": "UNMEASURED",
     "notes": "about five weeks after the reference month; the vehicles line is the German "
              "chain arriving as a domestic number"},
    {"name": "CSU external trade by country (zahranicni obchod)", "cadence": "monthly",
     "time_utc": "08:00", "source": "Cesky statisticky urad", "actual_series": "CZSO:trade_de",
     "expected_series": "UNMEASURED",
     "notes": "the German share of exports is the single number CZ-E is built on"},
    {"name": "CSU GDP flash estimate and structure (HDP bleskovy odhad)", "cadence": "quarterly",
     "time_utc": "08:00", "source": "Cesky statisticky urad", "actual_series": "CZSO:GDP_flash",
     "expected_series": "UNMEASURED",
     "notes": "about 30 days after the quarter; revised at 60 days, so the flash and the "
              "refined estimate are two different point-in-time objects"},
    {"name": "CNB foreign exchange reserves (devizove rezervy)", "cadence": "monthly",
     "time_utc": "13:00", "source": "Ceska narodni banka", "actual_series": "CNB:reserves",
     "expected_series": "n/a",
     "notes": "about seven business days after the month end; the floor era is a visible step "
              "and the gold tranche is a visible ramp from 2024"},
    {"name": "MF CR auction calendar and auction results (aukce statnich dluhopisu)",
     "cadence": "weekly", "time_utc": "10:00", "source": "Ministerstvo financi CR",
     "actual_series": "MFCR:auction_yield", "expected_series": "UNMEASURED",
     "notes": "the quarterly issuance calendar is published in advance and the results the same "
              "morning; the bid-to-cover and the non-resident allocation are the foreign flow"},
    {"name": "OTE day-ahead market results (vysledky denniho trhu)", "cadence": "daily",
     "time_utc": "11:55", "source": "OTE a.s.", "actual_series": "OTE:DA_price_CZ",
     "expected_series": "n/a",
     "notes": "published minutes after the coupled clearing; the CZ-DE spread is the coupling "
            "constraint's own measurement"},
    {"name": "ERU price decisions (cenova rozhodnuti) for regulated energy components",
     "cadence": "annual", "time_utc": "UNMEASURED", "source": "Energeticky regulacni urad",
     "actual_series": "ERU:regulated_component", "expected_series": "n/a",
     "notes": "published late in November for the following calendar year; a dated administered "
              "price that enters January's CPI mechanically"},
    {"name": "AutoSAP vehicle production statistics", "cadence": "monthly", "time_utc": "09:00",
     "source": "Sdruzeni automobiloveho prumyslu", "actual_series": "AUTOSAP:units",
     "expected_series": "n/a",
     "notes": "the industry's own count, published before the CSU's; it is the earliest read on "
              "the German chain's Czech limb"},
)

# --------------------------------------------------------------------------- holidays
#: THE STATUTE IS THE RULE (zakon c. 245/2000 Sb.). Seven STATE holidays and six OTHER holidays,
#: eleven of them on fixed solar dates and two derived from Easter. Czechia does NOT substitute a
#: holiday that falls at the weekend -- the day is simply lost, which is a liquidity fact a
#: naive "count the closed weekdays" study gets wrong in both directions.
FIXED_STATE: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Den obnovy samostatneho ceskeho statu / Novy rok"),
    (5, 8, "Den vitezstvi"),
    (7, 5, "Den slovanskych verozvestu Cyrila a Metodeje"),
    (7, 6, "Den upaleni mistra Jana Husa"),
    (9, 28, "Den ceske statnosti (svaty Vaclav)"),
    (10, 28, "Den vzniku samostatneho ceskoslovenskeho statu"),
    (11, 17, "Den boje za svobodu a demokracii"),
)
#: The "ostatni svatky" that are not state holidays but ARE closed days.
FIXED_OTHER: tuple[tuple[int, int, str], ...] = (
    (5, 1, "Svatek prace"),
    (12, 24, "Stedry den"),
    (12, 25, "1. svatek vanocni"),
    (12, 26, "2. svatek vanocni"),
)
#: Good Friday became a public holiday only from 2016 -- a closed day that did NOT exist before
#: then, and a regime break a study pooling 2010-2026 will silently mislabel as an open session.
GOOD_FRIDAY_FROM = 2016
#: The Easter-derived closed days, as (offset from Easter Sunday in days, name, first year).
EASTER_OFFSETS: tuple[tuple[int, str, int], ...] = (
    (-2, "Velky patek", GOOD_FRIDAY_FROM),
    (1, "Velikonocni pondeli", 1900),
)
#: No weekend substitution anywhere in the Czech statute.
WEEKEND_SUBSTITUTION = False


def easter_sunday(year: int) -> date:
    """Easter Sunday by the ANONYMOUS GREGORIAN ALGORITHM -- computed, never typed.

    A typed Easter table is a table that is wrong the first year nobody updates it, and both
    Czech Easter holidays and the whole Hungarian Whit Monday derive from this one date.
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
    """The Easter-derived Czech closed days for a year, respecting the year each became one."""
    base = easter_sunday(year)
    return {base + timedelta(days=off): name
            for off, name, since in EASTER_OFFSETS if year >= since}


def national_holidays(year: int) -> dict[date, str]:
    """Every statutory Czech closed day in a year: the eleven fixed dates plus the Easter pair.

    DERIVED FROM THE RULE, not typed: the fixed days come from the statute's own list and the
    movable pair from `easter_sunday`, so 2027 costs nothing and 2016's arrival of Good Friday
    is respected rather than backfilled.
    """
    out: dict[date, str] = {}
    for m, d, name in FIXED_STATE:
        out[date(year, m, d)] = name
    for m, d, name in FIXED_OTHER:
        out[date(year, m, d)] = name
    out.update(easter_holidays(year))
    return dict(sorted(out.items()))


def bank_holidays(year: int) -> dict[date, str]:
    """The banking calendar equals the statutory calendar: CERTIS settles on working days."""
    return national_holidays(year)


def market_holidays(year: int) -> dict[date, str]:
    """PSE closed days: the statutory calendar on WEEKDAYS only, because a Saturday closure
    costs no session and must never enter a holiday-liquidity sample as one."""
    return {d: n for d, n in bank_holidays(year).items() if d.weekday() < 5}


def lost_weekend_holidays(year: int) -> dict[date, str]:
    """The statutory days that fall at the weekend and are therefore LOST -- no substitute
    Monday exists in Czech law. This is the half of the calendar a naive closed-day count
    invents, and it is published here as its own series."""
    return {d: n for d, n in national_holidays(year).items() if d.weekday() >= 5}


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


def working_days(start: date, end: date) -> list[date]:
    """Every Czech working day in a closed span: weekdays that are not statutory holidays."""
    out: list[date] = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5 and cur not in national_holidays(cur.year):
            out.append(cur)
        cur += timedelta(days=1)
    return out


def utc_offset_hours(day: date) -> int:
    """Europe/Prague's UTC offset on a date: 1 in CET, 2 in CEST.

    The EU rule is the last Sunday of March at 01:00 UTC to the last Sunday of October at
    01:00 UTC. Computed rather than tabled, so the same 14:30 local decision can be mapped to
    its real UTC minute in any year without a timezone database on the box.
    """
    return 2 if dst_start(day.year) <= day < dst_end(day.year) else 1


def _last_sunday(year: int, month: int) -> date:
    day = date(year, month, 31) if month in (3, 10) else date(year, month, 30)
    return day - timedelta(days=(day.weekday() + 1) % 7)


def dst_start(year: int) -> date:
    """The last Sunday of March: CEST begins."""
    return _last_sunday(year, 3)


def dst_end(year: int) -> date:
    """The last Sunday of October: CET returns."""
    return _last_sunday(year, 10)


def decision_minute_utc(day: date) -> str:
    """The UTC minute a 14:30 Europe/Prague announcement actually lands on, for a given date.

    THE POINT OF THIS FUNCTION. The CNB's announcement minute is CONSTANT in local time and
    MOVES in UTC, so an intraday event window built in UTC and pooled across a year is two
    different windows averaged together. Every CZ event miner asks this per date.
    """
    return "12:30" if utc_offset_hours(day) == 2 else "13:30"


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_statute",
    "authority": "zakon c. 245/2000 Sb., o statnich svatcich, o ostatnich svatcich, o "
                 "vyznamnych dnech a o dnech pracovniho klidu; the PSE and the CNB both close "
                 "on the days it names",
    "rule": "ELEVEN FIXED SOLAR DAYS -- 1 Jan (Novy rok / Den obnovy samostatneho ceskeho "
            "statu), 1 May (Svatek prace), 8 May (Den vitezstvi), 5 Jul (Cyril a Metodej), "
            "6 Jul (Jan Hus), 28 Sep (Den ceske statnosti), 28 Oct (vznik Ceskoslovenska), "
            "17 Nov (Den boje za svobodu a demokracii), 24 Dec (Stedry den), 25 Dec and 26 Dec "
            "-- PLUS TWO EASTER-DERIVED DAYS computed with the anonymous Gregorian algorithm: "
            "Velky patek (Easter Sunday minus 2, a public holiday only FROM 2016) and "
            "Velikonocni pondeli (Easter Sunday plus 1). NO WEEKEND SUBSTITUTION: a holiday on "
            "a Saturday or Sunday is lost and no Monday is granted, so the number of closed "
            "SESSIONS varies by up to four days a year on the calendar alone. THE CLOCK ALSO "
            "MOVES: Europe/Prague is CET in winter and CEST in summer on the EU rule, so the "
            "CNB's fixed 14:30 local announcement lands at 13:30 UTC or 12:30 UTC depending on "
            "the date -- see `decision_minute_utc`.",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "national_rule": "see `rule`; `national_holidays(year)` is the computed form and is the "
                     "only place a date is produced",
    "market_rule": "the statutory calendar on weekdays; the PSE keeps its local hours all year "
                   "and therefore moves an hour in UTC at each DST boundary",
    "easter_rule": "anonymous Gregorian algorithm in `easter_sunday(year)`; Good Friday counts "
                   "only from 2016, which is a REGIME BREAK in the closed-day series",
    "substitution_rule": "NONE. Czech law grants no substitute day, so `lost_weekend_holidays` "
                         "is published as its own series rather than silently ignored",
    "dst_rule": "EU rule: CEST from the last Sunday of March to the last Sunday of October; "
                "`utc_offset_hours` and `decision_minute_utc` compute it",
    "table": {y: {d.isoformat(): n for d, n in national_holidays(y).items()}
              for y in (2024, 2025, 2026)},
    "status": {2024: "COMPUTED from the statute; Easter Sunday 2024-03-31, so Velky patek "
                     "2024-03-29 and Velikonocni pondeli 2024-04-01",
               2025: "COMPUTED from the statute; Easter Sunday 2025-04-20, so Velky patek "
                     "2025-04-18 and Velikonocni pondeli 2025-04-21",
               2026: "COMPUTED from the statute; Easter Sunday 2026-04-05, so Velky patek "
                     "2026-04-03 and Velikonocni pondeli 2026-04-06"},
    "known_dates": {
        "2024-03-29": "Velky patek, computed; a closed day that did not exist before 2016",
        "2025-04-21": "Velikonocni pondeli, computed from Easter 2025-04-20",
        "2026-04-06": "Velikonocni pondeli, computed from Easter 2026-04-05",
        "2026-11-17": "Den boje za svobodu a demokracii, a fixed solar date certain in any year",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "bank_fn": bank_holidays,
    "easter_fn": easter_sunday,
    "lost_fn": lost_weekend_holidays,
    "utc_offset_fn": utc_offset_hours,
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "MF CR holder structure of Czech state debt (drzitelska struktura)",
     "root": "https://www.mfcr.cz/cs/rozpoctova-politika/rizeni-statniho-dluhu",
     "fields": ("non_resident_share_pct", "by_holder_type", "by_instrument", "outstanding_czk"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "13:00", "lag_days": 30,
     "licence": "free, public", "available": True,
     "why": "the ONLY published measure of foreign positioning in Czech koruna assets; it rose "
            "through the floor era as the convergence trade was put on and fell after the exit, "
            "which is the positioning series CZ-D is built on",
     "pit_warning": "a month stale and revised; it conditions an era or a quarter, never a week"},
    {"name": "CNB foreign exchange reserves and their composition",
     "root": "https://www.cnb.cz/cs/financni-trhy/devizove-rezervy/",
     "fields": ("reserves_eur", "currency_composition", "equity_tranche_share", "gold_tonnes"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "13:00", "lag_days": 7,
     "licence": "free, public", "available": True,
     "why": "the other side of the same trade: what the CNB bought while the offshore accounts "
            "were selling it EUR at 27.00, and the equity and gold tranches it now runs",
     "pit_warning": "the monthly headline is prompt; the COMPOSITION is annual and much later, "
                    "so an equity-tranche claim is an annual conditioner and not a monthly one"},
    {"name": "CNB banking sector open FX position and the corporate forward book (ARAD)",
     "root": "https://www.cnb.cz/arad/",
     "fields": ("bank_open_fx_position", "fx_derivatives_outstanding", "corporate_forwards"),
     "frequency": "monthly", "snapshot": "month end", "publish_utc": "13:00", "lag_days": 45,
     "licence": "free, public (ARAD open time series)", "available": True,
     "why": "the exporter hedging book is the one recurring CZK flow that is not a policy act; "
            "ARAD publishes the aggregate as a machine-readable time series",
     "pit_warning": "six weeks late; a state variable for an era, never a trigger"},
    {"name": "PSE / CDCP foreign investor share of Prague market turnover",
     "root": "https://www.pse.cz/en/statistics",
     "fields": ("foreign_turnover_share", "by_member", "by_instrument"),
     "frequency": "monthly", "snapshot": "calendar month", "publish_utc": "12:00",
     "lag_days": 15, "licence": "free, public", "available": True,
     "why": "the equity-side foreign flow; small and concentrated, which BOUNDS what CZ-K can "
            "ever claim rather than licensing a claim",
     "pit_warning": "turnover share is not ownership; it says who traded, not who holds"},
    {"name": "a CFTC or exchange-traded koruna positioning series",
     "root": "", "fields": (), "frequency": "n/a", "snapshot": "", "publish_utc": "",
     "lag_days": 0, "licence": "", "available": False,
     "why": "DECLARED ABSENT: no koruna future trades on any exchange the desk reads and no COT "
            "contract exists for CZK",
     "pit_warning": "DOES NOT EXIST: koruna positioning is UNMEASURED and is never proxied by "
                    "the EUR COT leg, which is a position in the euro and not in the koruna"},
)

# --------------------------------------------------------------------------- terminology
#: CZECH IS A LATIN SCRIPT WITH ITS OWN LETTERS, AND THAT IS EXACTLY THE TRAP. A crawler that
#: strips diacritics reads "kurzovy zavazek" and misses "kurzovy závazek"; a crawler that
#: searches in English reads the Reuters summary of a CNB decision and never the decision. Every
#: group below carries the Czech term with its háčky and čárky, and the tests assert it.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "CZ-A": ("Česká národní banka", "bankovní rada", "měnověpolitické rozhodnutí",
             "dvoutýdenní repo sazba", "2T repo sazba", "inflační cíl", "Zpráva o měnové "
             "politice", "záznam z jednání bankovní rady", "hlasování bankovní rady",
             "diskontní sazba", "lombardní sazba", "úroková sazba", "prognóza ČNB"),
    "CZ-B": ("kurzový závazek", "devizové intervence", "oslabení koruny", "opuštění kurzového "
             "závazku", "hladina 27 korun za euro", "asymetrický závazek", "devizový trh",
             "kurz koruny", "posílení koruny", "kurzy devizového trhu", "deviza"),
    "CZ-C": ("devizové rezervy", "správa devizových rezerv", "akciová složka rezerv",
             "zlaté rezervy", "nákup zlata", "výnos z rezerv", "kurzová ztráta",
             "záporný vlastní kapitál ČNB", "bilance centrální banky"),
    "CZ-D": ("spekulace na posílení koruny", "carry trade", "korunové pozice",
             "zahraniční investoři", "držitelská struktura státního dluhu", "úrokový diferenciál",
             "sazbový rozdíl", "nerezidenti", "korunový dluhopis"),
    "CZ-E": ("průmyslová produkce", "automobilový průmysl", "zakázky v průmyslu",
             "Sdružení automobilového průmyslu", "subdodavatel", "výroba automobilů",
             "zahraniční obchod", "vývoz do Německa", "dodavatelský řetězec",
             "zpracovatelský průmysl", "index nákupních manažerů"),
    "CZ-F": ("denní trh s elektřinou", "OTE", "spotová cena elektřiny", "propojení trhů",
             "přeshraniční přenos", "ČEPS", "přenosová soustava", "vývoz elektřiny",
             "emisní povolenky", "hnědé uhlí", "jaderná elektrárna", "plynová elektrárna"),
    "CZ-G": ("aukce státních dluhopisů", "Ministerstvo financí", "emisní kalendář",
             "státní pokladniční poukázka", "výnos do splatnosti", "poptávka v aukci",
             "státní dluh", "financování státního dluhu", "primární dealer"),
    "CZ-H": ("Český statistický úřad", "index spotřebitelských cen", "míra inflace",
             "hrubý domácí produkt", "bleskový odhad", "nezaměstnanost", "maloobchodní tržby",
             "mzdy", "statistická revize", "meziroční růst"),
    "CZ-I": ("hypoteční úvěr", "refixace hypotéky", "fixace úrokové sazby", "úvěrové standardy",
             "ukazatel LTV", "ukazatel DSTI", "ukazatel DTI", "stavební spoření",
             "domácnosti a úspory", "zadlužení domácností"),
    "CZ-J": ("evropské fondy", "Národní plán obnovy", "kohezní politika", "čerpání dotací",
             "platební agentura", "operační program", "čistá pozice vůči rozpočtu EU",
             "dotační titul"),
    "CZ-K": ("Burza cenných papírů Praha", "index PX", "objem obchodů", "Centrální depozitář "
             "cenných papírů", "vypořádání obchodu", "dividendová sezóna",
             "likvidita trhu", "zahraniční podíl na obchodování"),
    "CZ-L": ("státní svátek", "Velký pátek", "Velikonoční pondělí", "den pracovního klidu",
             "Štědrý den", "letní čas", "zimní čas", "obchodní den", "zavírací den",
             "Den české státnosti"),
    "CZ-M": ("Energetický regulační úřad", "cenové rozhodnutí", "regulovaná složka ceny",
             "zastropování cen energií", "úsporný tarif", "distribuční poplatek",
             "cena plynu pro domácnosti", "regulované ceny"),
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

#: The letters that make a string CZECH rather than de-accented mush. A test asserts that the
#: terminology and the crawlable sources' queries carry them.
_CZECH_CHARS = "áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ"
#: The three letters that are Czech/Slovak and essentially nothing else in Europe: ř, ě and ů.
#: A pack that carries only á/é/í could be Spanish or Hungarian; one that carries ř is Czech.
_CZECH_UNIQUE_CHARS = "řěůŘĚŮ"


def has_czech(text: str) -> bool:
    """True when the text carries at least one Czech diacritic."""
    return any(ch in _CZECH_CHARS for ch in str(text))


def has_czech_unique(text: str) -> bool:
    """True when the text carries ř, ě or ů -- letters that are Czech and almost nothing else."""
    return any(ch in _CZECH_UNIQUE_CHARS for ch in str(text))


def czech_terms(terminology: Mapping[str, Iterable[str]] | None = None) -> list[str]:
    rows = TERMINOLOGY if terminology is None else terminology
    return [t for terms in rows.values() for t in terms if has_czech(t)]


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
    labels. `queries` are native-script terms, never translations. `machine_use_allowed=True`
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
        "cz_cnb", "Česká národní banka: decisions, minutes and vote splits, the Monetary Policy "
                  "Report, the declared exchange rates, the reserves and the ARAD time series",
        layer="official",
        roots=("https://www.cnb.cz/cs/menova-politika/mp-rozhodnuti/",
               "https://www.cnb.cz/cs/menova-politika/zpravy-o-menove-politice/",
               "https://www.cnb.cz/cs/financni-trhy/devizove-rezervy/",
               "https://www.cnb.cz/arad/"),
        queries=("měnověpolitické rozhodnutí ČNB", "záznam z jednání bankovní rady",
                 "2T repo sazba", "kurzy devizového trhu", "devizové rezervy ČNB",
                 "Zpráva o měnové politice", "prognóza inflace ČNB", "kurzový závazek"),
        languages=("cs", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (cnb.cz terms)",
        notes="the decision is stamped at a FIXED 14:30 local minute and the minutes eight days "
              "later carry the vote split, so this one root gives both the event and the "
              "dispersion measure a single policy rate cannot carry"),
    source_class(
        "cz_czso", "Český statistický úřad: CPI, GDP, industrial production and orders, "
                   "external trade by country, wages, and the public database VDB",
        layer="official",
        roots=("https://www.czso.cz/csu/czso/indexy-spotrebitelskych-cen-inflace",
               "https://www.czso.cz/csu/czso/prumysl_energetika",
               "https://www.czso.cz/csu/czso/zahranicni_obchod",
               "https://vdb.czso.cz/vdbvo2/"),
        queries=("index spotřebitelských cen", "míra inflace", "průmyslová produkce",
                 "nové zakázky v průmyslu", "zahraniční obchod se zbožím", "vývoz do Německa",
                 "bleskový odhad HDP", "veřejná databáze ČSÚ"),
        languages=("cs", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (CC BY 4.0 for VDB)",
        notes="VDB is a queryable open database rather than a wall of PDFs, which is why the "
              "Czech release clock is one of the few on this desk that a collector can fill "
              "without a scraper that breaks every redesign"),
    source_class(
        "cz_mfcr", "Ministerstvo financí ČR: the state debt strategy, the quarterly issuance "
                   "calendar, auction results, the holder structure and the budget",
        layer="official",
        roots=("https://www.mfcr.cz/cs/rozpoctova-politika/rizeni-statniho-dluhu",
               "https://www.mfcr.cz/cs/rozpoctova-politika/statni-rozpocet",
               "https://www.mfcr.cz/cs/verejny-sektor/makroekonomika"),
        queries=("emisní kalendář státních dluhopisů", "výsledky aukce státních dluhopisů",
                 "držitelská struktura státního dluhu", "strategie financování",
                 "státní pokladniční poukázky", "makroekonomická predikce ministerstva financí",
                 "státní rozpočet"),
        languages=("cs", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the issuance calendar is published a QUARTER AHEAD, so the auction clock is "
              "knowable in advance -- a dated forced-supply event, which is rare"),
    source_class(
        "cz_esbirka", "Sbírka zákonů and e-Sbírka: the gazette where every price decision, tax "
                      "change, holiday statute and energy cap becomes citable",
        layer="official",
        roots=("https://www.e-sbirka.cz", "https://www.zakonyprolidi.cz",
               "https://www.mvcr.cz/clanek/sbirka-zakonu.aspx"),
        queries=("Sbírka zákonů", "nařízení vlády cena energie", "zákon o státních svátcích",
                 "cenové rozhodnutí ERÚ", "novela zákona o daních", "účinnost od 1. ledna"),
        languages=("cs",), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (official gazette)",
        notes="FULLY DIGITISED back to 1945 and free, which is why no archive claim in this "
              "pack has to rest on a press report the way the Moroccan duty decrees do"),
    source_class(
        "cz_eru", "Energetický regulační úřad: the annual price decisions, the regulated "
                  "components, the market reports and the supplier-of-last-resort rules",
        layer="official",
        roots=("https://www.eru.cz/cenova-rozhodnuti", "https://www.eru.cz/zpravy-o-trhu"),
        queries=("cenové rozhodnutí ERÚ elektřina", "regulovaná složka ceny",
                 "cena distribuce plynu", "zpráva o trhu s elektřinou",
                 "dodavatel poslední instance", "zastropování cen energií"),
        languages=("cs",), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the regulated component is fixed in NOVEMBER for the following calendar year and "
              "enters January's CPI mechanically -- an administered price with a known date, "
              "which is the cleanest kind of event this desk can test"),
    source_class(
        "cz_nku_eu", "Nejvyšší kontrolní úřad and the European Commission: audit findings on EU "
                     "fund absorption, the Národní plán obnovy milestones and the payment "
                     "decisions", layer="official",
        roots=("https://www.nku.cz/cz/publikace-a-dokumenty/kontrolni-zavery/",
               "https://www.planobnovycr.cz",
               "https://commission.europa.eu/business-economy-euro/economic-recovery/"
               "recovery-and-resilience-facility_en"),
        queries=("kontrolní závěr NKÚ", "čerpání evropských fondů", "Národní plán obnovy",
                 "žádost o platbu Evropské komisi", "milníky a cíle", "operační program"),
        languages=("cs", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the EU payment request and its approval are DATED political events with a "
              "measurable EUR-to-CZK conversion behind them; the NKÚ is the one body that says "
              "out loud when absorption is not happening"),
    # ---- institutional
    source_class(
        "cz_pse_cdcp", "Burza cenných papírů Praha and the Centrální depozitář cenných papírů: "
                       "the PX composition, turnover statistics, the foreign share, the trading "
                       "calendar and the settlement rules", layer="institutional",
        roots=("https://www.pse.cz/en/statistics", "https://www.pse.cz/indexy/hodnoty-indexu",
               "https://www.cdcp.cz"),
        queries=("index PX", "objem obchodů na burze", "obchodní kalendář burzy",
                 "vypořádání obchodů", "Centrální depozitář cenných papírů",
                 "zahraniční podíl na obchodování"),
        languages=("cs", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the trading calendar is where the statutory holiday rule becomes a SESSION fact; "
              "the PX itself is a transmission target and never an instrument here"),
    source_class(
        "cz_cfbf", "Czech Financial Benchmark Facility: the PRIBOR fixings, the panel and the "
                   "benchmark methodology", layer="institutional",
        roots=("https://www.czechfbf.cz", "https://www.cnb.cz/cs/financni-trhy/penezni-trh/"),
        queries=("PRIBOR fixing", "úroková sazba na peněžním trhu", "panel bank",
                 "metodika referenční sazby", "sazby peněžního trhu"),
        languages=("cs", "en"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="PRIBOR is the carry leg of every koruna position; the fixing moved from the CNB "
              "to a private administrator in 2017, which is a METHODOLOGY break inside the "
              "series and must not be pooled across"),
    source_class(
        "cz_bank_research", "Openly published Czech bank research: Patria Finance, Komerční "
                            "banka (Ekonomický výzkum), ČSOB, Česká spořitelna (Erste) and "
                            "Raiffeisenbank", layer="institutional",
        roots=("https://www.patria.cz/ekonomika.html", "https://www.kb.cz/cs/o-bance/vse-o-kb/"
               "ekonomicky-vyzkum", "https://www.csob.cz/portal/csob/ekonomicke-vyhledy"),
        queries=("výhled ČNB sazby", "predikce inflace", "komentář k rozhodnutí ČNB",
                 "výhled kurzu koruny", "makroekonomická prognóza banky", "týdenní přehled trhů"),
        languages=("cs", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free notes; some behind registration",
        notes="the pre-meeting consensus these desks publish is the EXPECTATION a CNB surprise "
              "is measured against -- kept as a measurement object, never as a view adopted"),
    source_class(
        "cz_associations", "Industry bodies: Svaz průmyslu a dopravy ČR, Sdružení "
                           "automobilového průmyslu (AutoSAP), Česká bankovní asociace and the "
                           "Hospodářská komora", layer="institutional",
        roots=("https://www.spcr.cz", "https://autosap.cz/statistiky/",
               "https://cbaonline.cz", "https://www.komora.cz"),
        queries=("statistiky výroby vozidel", "Sdružení automobilového průmyslu",
                 "průzkum mezi podniky", "nedostatek pracovních sil",
                 "hypoteční trh statistiky", "energetické náklady průmyslu"),
        languages=("cs",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="AutoSAP publishes vehicle production BEFORE the statistics office publishes "
              "industrial production, so it is the earliest domestic read on the German chain"),
    # ---- academic
    source_class(
        "cz_academic", "CERGE-EI, IES FSV UK, VŠE Praha, Masarykova univerzita and the CNB "
                       "Working Paper Series -- the floor is one of the most studied natural "
                       "experiments in European monetary economics", layer="academic",
        roots=("https://www.cerge-ei.cz/publications", "https://ies.fsv.cuni.cz/en/research",
               "https://www.cnb.cz/en/economic-research/research-publications/cnb-working-paper-"
               "series/", "https://openalex.org"),
        queries=("kurzový závazek účinnost", "exchange rate commitment Czech National Bank",
                 "pass-through kurzu do cen", "efektivní dolní mez úrokových sazeb",
                 "transmise měnové politiky", "dopad devizových intervencí"),
        languages=("cs", "en"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access / publisher terms",
        notes="the CNB funds and publishes research ON ITS OWN INTERVENTION, which is unusual "
              "and useful: the bank's own estimate of the floor's pass-through is the mechanism "
              "source for CZ-B and remains a hypothesis until the desk reproduces it"),
    source_class(
        "cz_energy_academic", "ČVUT, VŠB-TU Ostrava and the energy institutes: merit-order "
                              "models, cross-border capacity studies and lignite phase-out "
                              "scenarios", layer="academic",
        roots=("https://www.cvut.cz", "https://www.vsb.cz",
               "https://www.mpo.gov.cz/cz/energetika/statistika/"),
        queries=("merit order elektrárny", "mezní cena elektřiny", "přeshraniční kapacita",
                 "útlum hnědého uhlí", "energetická bilance ČR", "spotřeba elektřiny průmyslem"),
        languages=("cs", "en"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="open access",
        notes="the merit-order studies are what make CZ-F a MECHANISM rather than a "
              "correlation: they say which plant is marginal at which load, which is the size "
              "and the sign of the gas leg"),
    # ---- practitioner
    source_class(
        "cz_patria_kurzy", "The Czech market desk press: Patria.cz, Kurzy.cz, Roklen24, "
                           "Investiční web and the brokers' daily commentary",
        layer="practitioner",
        roots=("https://www.patria.cz", "https://www.kurzy.cz/zpravy/",
               "https://roklen24.cz", "https://www.investicniweb.cz"),
        queries=("koruna vůči euru dnes", "komentář k aukci dluhopisů", "sazby ČNB očekávání",
                 "pražská burza uzavření", "výhled na trh s elektřinou", "úrokový diferenciál"),
        languages=("cs",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="Patria carries the auction and decision commentary within minutes and Kurzy.cz "
              "is the de facto national quote page; together they are the closest thing this "
              "market has to a consensus tape"),
    source_class(
        "cz_mortgage_desk", "The mortgage and deposit practitioners: Hypoindex (Fincentrum & "
                            "Swiss Life Select), Golem Finance, Broker Consulting and the "
                            "comparison sites", layer="practitioner",
        roots=("https://www.hypoindex.cz", "https://www.penize.cz",
               "https://www.mesec.cz/hypoteky/"),
        queries=("Fincentrum Hypoindex", "průměrná sazba hypotéky", "refixace hypotéky",
                 "objem nových hypoték", "úrokové sazby vkladů", "stavební spoření úroky"),
        languages=("cs",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="publisher terms",
        notes="Hypoindex publishes the average new-mortgage rate MONTHLY and years before the "
              "refixation wave shows up in consumption -- the lead series of CZ-I"),
    # ---- retail ecology
    source_class(
        "cz_retail_forums", "Czech retail communities: r/czech and r/Czechia investing threads, "
                            "the Kurzy.cz and Patria discussion boards, Facebook investing "
                            "groups and the Czech personal-finance blogs", layer="retail_ecology",
        roots=("https://www.reddit.com/r/czech/", "https://www.kurzy.cz/diskuze/",
               "https://www.facebook.com/groups/investoriCZ"),
        queries=("kam investovat peníze", "spoření versus investice", "koruna posílí nebo "
                 "oslabí", "nákup eura kurz", "zkušenosti s brokerem", "daň z investic"),
        languages=("cs",), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="KEPT AT LOW WEIGHT and never a source of edge: what it dates is the RETAIL "
              "CONVERSION episode -- the weeks when Czech households moved term deposits into "
              "funds or into euro cash, which is a real CZ-I observable"),
    source_class(
        "cz_retail_brokers", "Czech-language retail broker marketing, YouTube and Telegram "
                             "trading channels, and the prop-firm affiliates targeting Czech "
                             "retail", layer="retail_ecology",
        roots=("https://www.youtube.com/results?search_query=trading+česky",
               "https://t.me/s/tradingcz"),
        queries=("obchodování na forexu", "pákový efekt", "signály zdarma", "prop firma",
                 "demo účet", "zlato obchodování"),
        languages=("cs",), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="platform terms; public posts only",
        notes="ESMA leverage caps apply here (Czechia is an EU member state), so this ground is "
              "a REGULATED retail base rather than an offshore one; kept because the XAUUSD and "
              "GER40 stop clusters it advertises are a real microstructure observable"),
    # ---- app ecosystem
    source_class(
        "cz_official_apis", "The machine-readable official endpoints: the CNB daily exchange "
                            "rate file, the ARAD time-series API, the CSU VDB API and the "
                            "state open-data catalogue", layer="app_ecosystem",
        roots=("https://www.cnb.cz/cs/financni-trhy/devizovy-trh/kurzy-devizoveho-trhu/"
               "kurzy-devizoveho-trhu/denni_kurz.txt",
               "https://www.cnb.cz/arad/", "https://vdb.czso.cz/vdbvo2/",
               "https://data.gov.cz"),
        queries=("denní kurz ČNB soubor", "ARAD časové řady", "otevřená data ČR",
                 "veřejná databáze API", "strojově čitelná data"),
        languages=("cs", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public open data",
        notes="THE ONE LAYER THAT USUALLY DISAPPOINTS AND HERE DOES NOT: denni_kurz.txt is a "
              "stable plain-text endpoint that has published the official koruna rate for "
              "years, so the CZ fixing series needs no scraper at all"),
    source_class(
        "cz_retail_apps", "The apps a Czech actually invests through: Portu, Fondee, XTB CZ, "
                          "Degiro, Patria Finance, and the bank apps George (Česká spořitelna) "
                          "and ČSOB Smart", layer="app_ecosystem",
        roots=("https://www.portu.cz", "https://www.fondee.cz", "https://www.xtb.com/cz",
               "https://www.patria.cz/sluzby.html"),
        queries=("investiční aplikace recenze", "poplatky u brokera", "portfolio ETF",
                 "spořicí účet sazba", "investice do fondů", "pravidelné investování"),
        languages=("cs",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="app store and publisher terms",
        notes="the robo-advisers publish AUM and inflow updates, which is the only near-real-"
              "time read on the household savings migration CZ-I is about"),
    # ---- media
    source_class(
        "cz_wire_press", "ČTK (the state wire), Hospodářské noviny, E15, Seznam Zprávy, "
                         "iDNES Ekonomika, ČT24 and Euro.cz", layer="media",
        roots=("https://www.ctk.cz", "https://archiv.hn.cz", "https://www.e15.cz",
               "https://www.seznamzpravy.cz/sekce/ekonomika", "https://ct24.ceskatelevize.cz"),
        queries=("ČNB zvýšila sazby", "koruna oslabila", "ceny energií pro domácnosti",
                 "vláda schválila rozpočet", "Škoda Auto výroba", "ČEZ výsledky"),
        languages=("cs",), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", licence="publisher terms",
        notes="ČTK carries the minute of a decision or a government decree when the "
              "institution's own page carries only a date; Hospodářské noviny is the one outlet "
              "that reports the POLITICS of an energy cap rather than only its number"),
    source_class(
        "cz_licensed_terminals", "Licensed terminals and price reporting agencies: Bloomberg, "
                                 "LSEG/Refinitiv, and ICIS / Argus / Montel for Central "
                                 "European power, gas and carbon assessments", layer="media",
        roots=("https://www.icis.com", "https://www.montelnews.com"),
        queries=("Czech power baseload assessment", "CEGH gas price", "EUA settlement",
                 "CZ DE spread day ahead"),
        languages=("en",), access_label="LICENSED", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="subscription; terms forbid machine extraction",
        machine_use_allowed=True,
        notes="REGISTERED, NEVER SCRAPED: the forward power and carbon curves are paywalled, so "
              "CZ-F is measured on the FUEL leg and the SMELTER leg that are executable and on "
              "OTE's own published day-ahead prints -- the absence is named, not worked around"),
    # ---- archive
    source_class(
        "cz_arad_archive", "ARAD and the CSU statistical yearbooks: the long history of the "
                           "policy rate, the exchange rate, the reserves and the national "
                           "accounts, including discontinued series", layer="archive",
        roots=("https://www.cnb.cz/arad/", "https://www.czso.cz/csu/czso/statisticka-rocenka-"
               "ceske-republiky", "https://vdb.czso.cz/vdbvo2/"),
        queries=("ARAD časové řady historie", "statistická ročenka", "historie kurzu koruny",
                 "vývoj repo sazby", "ukončená časová řada", "metodická změna"),
        languages=("cs", "en"), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="ARAD keeps the FULL history including the floor era at daily frequency, which is "
              "why the CZ-B regime break can be measured rather than argued about"),
    source_class(
        "cz_gazette_library", "The Sbírka zákonů full run, the Kramerius digital library of the "
                              "Národní knihovna, and the Parliament's stenographic records",
        layer="archive",
        roots=("https://www.zakonyprolidi.cz/cs/rocniky", "https://www.digitalniknihovna.cz",
               "https://www.psp.cz/eknih/"),
        queries=("Sbírka zákonů ročník", "digitální knihovna Kramerius", "stenografický zápis "
                 "sněmovny", "historické cenové rozhodnutí", "archiv úředního věstníku"),
        languages=("cs",), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public; some library items rights-restricted",
        notes="a fully digitised gazette back to 1945 means every administered-price and tax "
              "date in this pack can be CITED rather than press-reported -- the discipline the "
              "Moroccan pack could not have"),
    source_class(
        "cz_wayback", "web.archive.org snapshots of the ERÚ price pages, the MF CR issuance "
                      "calendar and the OTE result pages, all of which overwrite in place",
        layer="archive",
        roots=("https://web.archive.org/web/*/eru.cz*", "https://web.archive.org/web/*/ote-cr.cz*",
               "https://web.archive.org/web/*/mfcr.cz*"),
        queries=("ERÚ cenové rozhodnutí archiv", "OTE denní trh archiv",
                 "emisní kalendář archiv"),
        languages=("cs", "en"), access_label="PUBLIC_ARCHIVE", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="Internet Archive terms",
        notes="the OTE result page and the MF CR calendar page show the CURRENT state and keep "
              "no vintage, so a point-in-time reconstruction of what was KNOWN on a date exists "
              "only in a crawl somebody took"),
    # ---- physical economy
    source_class(
        "cz_ote_power", "OTE a.s. and the coupled day-ahead market: hourly prices and volumes "
                        "for the Czech bidding zone and the SDAC clearing",
        layer="physical_economy",
        roots=("https://www.ote-cr.cz/cs/statistika/denni-trh",
               "https://www.ote-cr.cz/cs/kratkodobe-trhy/elektrina/denni-trh"),
        queries=("denní trh s elektřinou výsledky", "hodinová cena elektřiny",
                 "sedlová a špičková cena", "propojení trhů SDAC", "vnitrodenní trh"),
        languages=("cs", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the CZ day-ahead print is published minutes after a COUPLED clearing, so the "
              "CZ-DE spread measures the interconnector's binding constraint directly -- the "
              "one physical observable in this pack with no reporting lag at all"),
    source_class(
        "cz_ceps_grid", "ČEPS (the transmission system operator), NET4GAS and the ENTSO-E "
                        "transparency platform: load, generation by fuel, cross-border physical "
                        "flows, outages and gas entry-exit flows", layer="physical_economy",
        roots=("https://www.ceps.cz/cs/data", "https://www.net4gas.cz/informace-o-prepravnim-"
               "systemu/", "https://transparency.entsoe.eu"),
        queries=("ČEPS data o zatížení", "přeshraniční toky elektřiny", "výroba podle zdroje",
                 "odstávka bloku elektrárny", "přeprava plynu kapacita", "saldo zahraniční "
                 "výměny"),
        languages=("cs", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (ENTSO-E requires registration)",
        notes="a NUCLEAR OUTAGE at Temelín or Dukovany is a dated, published supply event that "
              "flips the Czech marginal plant to gas -- the cleanest XNGUSD trigger this pack "
              "has, and it is announced in advance on the REMIT/ENTSO-E feed"),
    source_class(
        "cz_industry_logistics", "AutoSAP production counts, Správa železnic freight data, the "
                                 "MPO energy balance and the ŘSD traffic counts -- the physical "
                                 "counterpart of a landlocked manufacturing economy",
        layer="physical_economy",
        roots=("https://autosap.cz/statistiky/", "https://www.spravazeleznic.cz",
               "https://www.mpo.gov.cz/cz/energetika/statistika/"),
        queries=("výroba vozidel v ČR", "nákladní železniční doprava", "energetická bilance",
                 "spotřeba plynu v průmyslu", "intenzita dopravy", "odstávka výroby závodu"),
        languages=("cs",), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="CZECHIA IS LANDLOCKED and has no port authority, which is the one genuine "
              "physical absence in this pack; the layer is therefore built on power, gas, rail "
              "and plant-level production counts instead of berths and AIS"),
    # ---- source graph
    source_class(
        "cz_source_graph", "Who cites whom: ČNB → Patria and the bank research desks → Kurzy.cz "
                           "and the wires → the retail forums; the government decree → the "
                           "Sbírka zákonů → ERÚ's price decision → Hospodářské noviny",
        layer="source_graph",
        roots=("https://www.cnb.cz/cs/cnb-news/", "https://www.patria.cz",
               "https://www.kurzy.cz/zpravy/"),
        queries=("podle informací ČTK", "uvedl mluvčí ČNB", "podle zdrojů z ministerstva",
                 "jak uvedl analytik", "citováno podle", "podle návrhu nařízení vlády"),
        languages=("cs",), access_label="PUBLIC", credibility="UNKNOWN",
        predictive_state="UNTESTED", licence="derived from the public sources above",
        notes="'podle zdrojů z ministerstva' marks the unattributed leak that precedes a "
              "regulated-price or tax decree in this country by a day or two; the graph is how "
              "a leak is told from a repost, and it is the only way to date a CZ-M decision "
              "before the gazette prints it"),
)

#: NO LAYER IS ABSENT FOR CZECHIA, and that is a MEASUREMENT rather than an omission. Every one
#: of the ten has a real root above: an open-data central bank with a public API, a queryable
#: statistics database, a fully digitised gazette back to 1945, a live native-language retail
#: ground and a transparency platform for the grid. The one genuine physical absence -- the
#: country is landlocked and has no port authority -- is named INSIDE the physical-economy layer
#: (`cz_industry_logistics`) rather than used to declare the layer empty, because the layer is
#: not empty: it is built on power, gas and rail instead.
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


#: NATIVE QUERY TERRITORIES -- what the deep-forest miner actually types into a Czech search box,
#: one territory per layer. These are NOT the source rows' own queries repeated: they are the
#: broader phrases a crawler expands a layer with when it is looking for grounds this pack has
#: not named yet, which is the half of discovery a fixed root list cannot do.
QUERY_TERRITORIES: dict[str, tuple[str, ...]] = {
    "official": ("měnověpolitické rozhodnutí bankovní rady", "tisková zpráva ČNB sazby",
                 "cenové rozhodnutí Energetického regulačního úřadu",
                 "emisní kalendář státních dluhopisů ministerstvo financí",
                 "index spotřebitelských cen ČSÚ tisková zpráva",
                 "nařízení vlády účinnost od ledna"),
    "institutional": ("obchodní kalendář Burzy cenných papírů Praha", "PRIBOR metodika fixingu",
                      "ekonomický výzkum komerční banky výhled",
                      "statistiky výroby AutoSAP měsíc", "Česká bankovní asociace prognóza",
                      "Svaz průmyslu a dopravy šetření"),
    "academic": ("kurzový závazek ČNB empirická studie", "transmise měnové politiky v ČR",
                 "pass-through kurzu koruny do inflace", "CERGE-EI working paper koruna",
                 "merit order model české elektroenergetiky", "refixace hypoték dopad na spotřebu"),
    "practitioner": ("analytik očekává rozhodnutí ČNB", "komentář k aukci státních dluhopisů",
                     "výhled kurzu koruny na konec roku", "Hypoindex průměrná sazba",
                     "denní zpráva z pražské burzy", "úrokový diferenciál koruna euro"),
    "retail_ecology": ("kam investovat v Česku diskuze", "koruna nebo euro co koupit",
                       "zkušenosti s investováním fórum", "spořicí účet nebo dluhopis",
                       "protiinflační dluhopisy diskuze", "daň z prodeje akcií Česko"),
    "app_ecosystem": ("denní kurz ČNB textový soubor", "ARAD API časové řady stažení",
                      "otevřená data ČSÚ rozhraní", "investiční aplikace poplatky srovnání",
                      "bankovní identita přihlášení", "robo advisor Česko výnosy"),
    "media": ("ČTK ekonomika depeše", "Hospodářské noviny energetika analýza",
              "Seznam Zprávy ekonomika rozbor", "ČT24 ekonomika rozhovor guvernér",
              "E15 trhy komentář", "iDNES ekonomika ceny energií"),
    "archive": ("Sbírka zákonů historické znění", "ARAD ukončená časová řada",
                "statistická ročenka České republiky archiv", "digitální knihovna Kramerius "
                "hospodářství", "stenografický zápis sněmovny rozpočet",
                "archiv tiskových zpráv ČNB"),
    "physical_economy": ("odstávka jaderného bloku Temelín", "přeshraniční toky elektřiny ČEPS",
                         "spotřeba plynu v průmyslu měsíc", "výroba osobních automobilů v ČR",
                         "nákladní doprava po železnici statistika",
                         "cena elektřiny na denním trhu OTE"),
    "source_graph": ("podle zdrojů z ministerstva financí", "uvedl mluvčí České národní banky",
                     "podle informací Hospodářských novin", "citoval analytik Patria Finance",
                     "jak dnes informovala ČTK", "podle návrhu, který má redakce k dispozici"),
}

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "CNB policy decisions, vote splits and the published forecast path",
     "source": "Ceska narodni banka", "coverage": "1993 onward; the published rate path "
                                                  "from 2008", "frequency": "8 per year",
     "publication_lag_days": 0.0, "revisions": "never revised", "licence": "free, public",
     "history_from": "1993-01", "pit_feasible": True,
     "assets": ("EURCZK", "USDCZK", "EURPLN"),
     "mechanism_families": ("policy_surprise", "event_reaction"),
     "how_to_fetch": "cnb.cz menova-politika/mp-rozhodnuti for the decision and the eight-day "
                     "minutes; ARAD series for the 2T repo history; the Monetary Policy Report "
                     "PDF for the published path"},
    {"name": "CNB declared daily exchange rates (kurzy devizoveho trhu)",
     "source": "Ceska narodni banka", "coverage": "1991 onward, every working day",
     "frequency": "daily", "publication_lag_days": 0.0, "revisions": "never",
     "licence": "free, public", "history_from": "1991-01", "pit_feasible": True,
     "assets": ("EURCZK", "USDCZK"), "mechanism_families": ("fixing", "administered_price"),
     "how_to_fetch": "the plain-text endpoint cnb.cz .../denni_kurz.txt for today and the "
                     "year-file variant for history; a stable machine-readable root that needs "
                     "no scraper"},
    {"name": "The EUR/CZK floor: the commitment, the intervention volumes and the exit",
     "source": "CNB decisions, balance of payments, reserve series and Article IV annexes",
     "coverage": "2013-11-07 to 2017-04-06", "frequency": "irregular, dated",
     "publication_lag_days": 30.0, "revisions": "the BoP intervention line is revised",
     "licence": "free, public", "history_from": "2013-11", "pit_feasible": True,
     "assets": ("EURCZK", "EURPLN", "EURHUF"),
     "mechanism_families": ("regime_break", "administered_price"),
     "how_to_fetch": "the two extraordinary decisions on cnb.cz; the monthly reserves series and "
                     "the BoP financial account in ARAD for the volumes; the era boundaries are "
                     "the two dates in FLOOR_REGIME"},
    {"name": "CNB foreign exchange reserves, composition, equity tranche and gold",
     "source": "Ceska narodni banka", "coverage": "1993 onward monthly; composition annual",
     "frequency": "monthly (headline) / annual (composition)", "publication_lag_days": 7.0,
     "revisions": "minor", "licence": "free, public", "history_from": "1993-01",
     "pit_feasible": True, "assets": ("US500", "EUSTX50", "XAUUSD"),
     "mechanism_families": ("institutional_flow", "central_bank_balance_sheet"),
     "how_to_fetch": "cnb.cz financni-trhy/devizove-rezervy monthly; the annual report's "
                     "reserve-management chapter for the equity share and the gold tonnage"},
    {"name": "CSU consumer price index and its regulated-energy component",
     "source": "Cesky statisticky urad", "coverage": "1991 onward",
     "frequency": "monthly", "publication_lag_days": 11.0, "revisions": "rebasing only",
     "licence": "free, public (CC BY 4.0 on VDB)", "history_from": "1991-01",
     "pit_feasible": True, "assets": ("EURCZK", "USDCZK"),
     "mechanism_families": ("release_surprise", "administered_price"),
     "how_to_fetch": "czso.cz CPI release plus the VDB query API for the COICOP breakdown; the "
                     "regulated-energy line is the ERU decision arriving in January"},
    {"name": "CSU industrial production, new orders and the vehicles line",
     "source": "Cesky statisticky urad", "coverage": "2000 onward", "frequency": "monthly",
     "publication_lag_days": 35.0, "revisions": "routinely revised one month back",
     "licence": "free, public", "history_from": "2000-01", "pit_feasible": True,
     "assets": ("GER40", "EUSTX50", "EURCZK"),
     "mechanism_families": ("release_surprise", "transfer"),
     "how_to_fetch": "czso.cz prumysl_energetika; VDB for the CZ-NACE 29 vehicles line, which "
                     "is the German chain arriving as a domestic number"},
    {"name": "CSU external trade by partner country and product group",
     "source": "Cesky statisticky urad", "coverage": "1993 onward", "frequency": "monthly",
     "publication_lag_days": 36.0, "revisions": "revised; the cross-border concept changed in "
                                                "2020, which is a series break",
     "licence": "free, public", "history_from": "1993-01", "pit_feasible": True,
     "assets": ("GER40", "EURCZK", "NETH25"),
     "mechanism_families": ("trade_cycle", "transfer"),
     "how_to_fetch": "czso.cz zahranicni_obchod; VDB for the by-country series -- the German "
                     "share is the single number CZ-E conditions on"},
    {"name": "CSU GDP flash estimate, refinement and structure",
     "source": "Cesky statisticky urad", "coverage": "1996 onward", "frequency": "quarterly",
     "publication_lag_days": 30.0, "revisions": "flash at 30 days, refined at 60, annual "
                                                "benchmark revisions",
     "licence": "free, public", "history_from": "1996-Q1", "pit_feasible": True,
     "assets": ("EURCZK", "EUSTX50"), "mechanism_families": ("release_surprise",),
     "how_to_fetch": "czso.cz HDP release; the FLASH and the REFINED estimate are two different "
                     "point-in-time objects and a study must say which it used"},
    {"name": "MF CR issuance calendar, auction results and bid-to-cover",
     "source": "Ministerstvo financi CR", "coverage": "2000 onward",
     "frequency": "weekly during the issuance season", "publication_lag_days": 0.0,
     "revisions": "never", "licence": "free, public", "history_from": "2000-01",
     "pit_feasible": True, "assets": ("EURCZK", "USDCZK"),
     "mechanism_families": ("calendar_settlement", "supply_event"),
     "how_to_fetch": "mfcr.cz rizeni-statniho-dluhu: the quarterly calendar A QUARTER AHEAD and "
                     "the results the same morning -- a dated forced-supply event"},
    {"name": "MF CR holder structure of state debt (the non-resident share)",
     "source": "Ministerstvo financi CR", "coverage": "2004 onward", "frequency": "monthly",
     "publication_lag_days": 30.0, "revisions": "minor", "licence": "free, public",
     "history_from": "2004-01", "pit_feasible": True, "assets": ("EURCZK", "EURPLN"),
     "mechanism_families": ("positioning", "institutional_flow"),
     "how_to_fetch": "mfcr.cz debt-management monthly report, the drzitelska struktura table; "
                     "the only published koruna positioning series that exists"},
    {"name": "OTE day-ahead electricity prices and volumes for the Czech zone",
     "source": "OTE a.s.", "coverage": "2002 onward, hourly", "frequency": "daily (hourly grid)",
     "publication_lag_days": 0.0, "revisions": "never", "licence": "free, public",
     "history_from": "2002-01", "pit_feasible": True, "assets": ("XNGUSD", "XALUSD", "GER40"),
     "mechanism_families": ("energy_complex", "administered_price"),
     "how_to_fetch": "ote-cr.cz statistika/denni-trh, CSV per day; the CZ-DE spread against the "
                     "German print measures the interconnector's binding constraint"},
    {"name": "CEPS and ENTSO-E: load, generation by fuel, outages and cross-border flows",
     "source": "CEPS a.s. and the ENTSO-E transparency platform",
     "coverage": "2010 onward, quarter-hourly", "frequency": "continuous",
     "publication_lag_days": 0.0, "revisions": "outage notices are amended",
     "licence": "free, public (ENTSO-E needs a free account)", "history_from": "2010-01",
     "pit_feasible": True, "assets": ("XNGUSD", "GER40", "XALUSD"),
     "mechanism_families": ("physical_supply", "event_reaction"),
     "how_to_fetch": "ceps.cz/cs/data for the Czech series and transparency.entsoe.eu for the "
                     "REMIT outage notices -- a Temelin or Dukovany block outage is announced "
                     "in advance and flips the marginal plant to gas"},
    {"name": "ERU annual price decisions and the regulated components",
     "source": "Energeticky regulacni urad", "coverage": "2001 onward",
     "frequency": "annual (published late November)", "publication_lag_days": 0.0,
     "revisions": "amended by decision", "licence": "free, public", "history_from": "2001-11",
     "pit_feasible": True, "assets": ("EURCZK", "XNGUSD"),
     "mechanism_families": ("administered_price", "release_surprise"),
     "how_to_fetch": "eru.cz/cenova-rozhodnuti; the decision is dated in November and enters "
                     "January's CPI mechanically, which is a known-in-advance inflation step"},
    {"name": "AutoSAP monthly vehicle production and the automotive chain",
     "source": "Sdruzeni automobiloveho prumyslu", "coverage": "1995 onward",
     "frequency": "monthly", "publication_lag_days": 12.0, "revisions": "rarely",
     "licence": "free, public", "history_from": "1995-01", "pit_feasible": True,
     "assets": ("GER40", "EUSTX50", "EURCZK"),
     "mechanism_families": ("transfer", "trade_cycle"),
     "how_to_fetch": "autosap.cz/statistiky monthly tables; published BEFORE the statistics "
                     "office's industrial production, so it is the earliest domestic read on "
                     "the German chain -- and it is an ACTOR-level series, never a share CFD"},
    {"name": "PRIBOR fixings and the CZK money-market curve",
     "source": "Czech Financial Benchmark Facility (CNB before 2017)",
     "coverage": "1992 onward", "frequency": "daily", "publication_lag_days": 0.0,
     "revisions": "never", "licence": "free, public", "history_from": "1992-01",
     "pit_feasible": True, "assets": ("EURCZK", "EURPLN", "EURHUF"),
     "mechanism_families": ("carry_funding", "fixing"),
     "how_to_fetch": "czechfbf.cz daily fixings and ARAD for history; NOTE the 2017 "
                     "administrator change, which is a methodology break inside the series"},
    {"name": "Hypoindex: the average new-mortgage rate, volumes and the refixation stock",
     "source": "Fincentrum & Swiss Life Select Hypoindex; CNB ARAD for the stock",
     "coverage": "2003 onward", "frequency": "monthly", "publication_lag_days": 20.0,
     "revisions": "minor", "licence": "publisher terms; ARAD free", "history_from": "2003-01",
     "pit_feasible": True, "assets": ("EURCZK", "EUSTX50"),
     "mechanism_families": ("credit_channel", "household_flow"),
     "how_to_fetch": "hypoindex.cz monthly release plus the ARAD loan-stock-by-fixation tables; "
                     "the refixation wave is the CZ-I lead series and it leads consumption by "
                     "the fixation length, not by a month"},
    {"name": "EU cohesion and Recovery and Resilience Facility payments to Czechia",
     "source": "European Commission; Ministerstvo pro mistni rozvoj; planobnovycr.cz",
     "coverage": "2014 onward (RRF from 2021)", "frequency": "irregular, dated",
     "publication_lag_days": 3.0, "revisions": "never", "licence": "free, public",
     "history_from": "2014-01", "pit_feasible": True, "assets": ("EURCZK", "EURPLN"),
     "mechanism_families": ("forced_flow", "event_reaction"),
     "how_to_fetch": "the Commission's RRF payment decisions and the Czech payment requests; "
                     "each approval is a dated EUR receipt the state converts into CZK"},
    {"name": "CNB macroprudential limits: LTV, DTI and DSTI and their announcement dates",
     "source": "Ceska narodni banka Financial Stability Report", "coverage": "2015 onward",
     "frequency": "semi-annual, with dated changes", "publication_lag_days": 0.0,
     "revisions": "never", "licence": "free, public", "history_from": "2015-06",
     "pit_feasible": True, "assets": ("EURCZK", "EUSTX50"),
     "mechanism_families": ("macroprudential", "credit_channel"),
     "how_to_fetch": "cnb.cz Zprava o financni stabilite plus the dated board decisions; the "
                     "limits were tightened, suspended in 2020 and restored, which is three "
                     "regime boundaries inside the mortgage channel"},
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    {"name": "The CNB bank board (bankovni rada)",
     "holds": "the 2W repo rate, the discount and Lombard corridor, a reserve pile that peaked "
              "above 70% of GDP, and the right to use the EXCHANGE RATE as the instrument when "
              "the rate is at its technical zero",
     "forced_to": ("decide at eight scheduled meetings a year and announce at a FIXED 14:30 "
                   "local minute", "publish the vote split eight days later",
                   "publish its own forecast interest-rate path four times a year",
                   "declare the official koruna rate every working day"),
     "when": "14:30 Europe/Prague on the meeting day -- 13:30 UTC in CET and 12:30 UTC in CEST, "
             "which is two different UTC windows and never one",
     "information": ("the staff forecast before the market sees it",
                     "the FX intervention book and the reserve position",
                     "the banking system's liquidity and the auction pipeline",
                     "the fiscal financing plan agreed with the Ministry of Finance"),
     "constraints": ("a published 2% target with a +/-1pp band, which makes a surprise "
                     "measurable against a number rather than a mood",
                     "a board that has voted against its own published path repeatedly",
                     "no euro-area membership and no ERM II, so no external commitment binds it",
                     "an effective lower bound that in 2013 left only the exchange rate"),
     "instruments": ("EURCZK", "USDCZK", "EURPLN"),
     "counterparties": ("the commercial banks at the 2W repo tender",
                        "the offshore accounts that bought koruna at the floor",
                        "the Ministry of Finance's debt desk",
                        "the exporters whose forward book it moves"),
     "observables": ("the decision and the vote split", "the published forecast path",
                     "the daily declared rate", "the monthly reserve series",
                     "the minutes' description of the risks"),
     "impact": "the rate decision moves the whole CZK curve and EURCZK directly, and unlike "
               "most packs on this desk the currency leg IS executable, so a CZ-A cell is a "
               "cell and not a proxy",
     "persistence": "the level persists between meetings by construction; the GUIDANCE in the "
                    "path persists for a quarter and is revised four times a year",
     "falsifier": "the same 14:30-local window on the four nearest non-meeting Thursdays, and "
                  "the same window on ECB decision days -- an effect that survives neither is a "
                  "weekday effect or a euro event wearing the CNB's hat",
     "notes": "THE FIXED MINUTE IS THE ASSET. Most of this desk's central banks announce 'in "
              "the afternoon'; this one announces at 14:30, so the event window needs no "
              "stamping work and only needs the DST correction"},
    {"name": "The CNB FX desk as the floor's unlimited counterparty (2013-2017)",
     "holds": "an open-ended commitment to sell koruna at 27.00 and the reserves it created",
     "forced_to": ("intervene without limit at the floor, at a price it had published",
                   "keep the commitment credible by repeating it at every meeting",
                   "absorb every euro the market wanted to sell at that level",
                   "exit without a announced date, which it did on 2017-04-06"),
     "when": "continuously between 2013-11-07 and 2017-04-06, concentrated in the last months "
             "when the exit was expected and the inflow accelerated",
     "information": ("the daily order flow arriving at the floor",
                     "its own intervention volumes before the balance of payments shows them",
                     "the composition of who was buying -- offshore versus domestic",
                     "the internal exit criteria and the board's tolerance"),
     "constraints": ("a balance sheet that grows without limit while the commitment holds",
                     "a currency mismatch that becomes a mark-to-market loss when the koruna "
                     "finally appreciates",
                     "a one-sided commitment: it defended a FLOOR and never a ceiling",
                     "public accountability for the losses in the annual report"),
     "instruments": ("EURCZK", "EURPLN", "EURHUF"),
     "counterparties": ("offshore macro funds running the convergence trade",
                        "the domestic banks intermediating them",
                        "the exporters who stopped hedging because the floor did it for them"),
     "observables": ("the reserve series stepping upward month after month",
                     "the balance of payments financial account",
                     "EURCZK pinned at 27.00 with no downside distribution",
                     "the forward points and the implied volatility collapsing"),
     "impact": "inside the era EURCZK's downside DID NOT EXIST; the tradable object was the "
               "pin itself and the exit, not the currency's own process",
     "persistence": "three years and five months -- long enough that a five-year estimation "
                    "window is mostly a measurement of a policy commitment",
     "falsifier": "the era's EURCZK distribution is indistinguishable from the surrounding "
                  "years' once the pin is removed -- if true, the regime break is cosmetic and "
                  "CZ-B's whole premise fails",
     "notes": "the reason this pack exists as its own department rather than a Polish annex"},
    {"name": "The CNB reserve management division (the equity and gold tranches)",
     "holds": "a reserve portfolio the size of the economy, part of it in global equities and, "
              "since 2024, a declared and growing gold allocation",
     "forced_to": ("invest the reserves the floor created rather than sit in negative-yielding "
                   "euro paper", "report the composition in the annual report",
                   "rebalance the equity tranche back to its target weights",
                   "publish the gold tonnage monthly"),
     "when": "rebalancing is continuous and disclosed annually; the gold purchases are reported "
             "monthly and have been a steady ramp since 2024",
     "information": ("its own rebalancing schedule and tolerance bands",
                     "the realised return and the currency attribution",
                     "the board's appetite for reported losses"),
     "constraints": ("a central bank with NEGATIVE equity for years, which is politically "
                     "expensive even when it is economically irrelevant",
                     "a mandate that puts liquidity and safety before return",
                     "disclosure that is ANNUAL for composition and monthly only for the "
                     "headline, so the flow is inferable and never observable live"),
     "instruments": ("US500", "EUSTX50", "XAUUSD"),
     "counterparties": ("the global index funds and custodians it invests through",
                        "the bullion market for the gold programme",
                        "the Czech taxpayer, who owns the loss"),
     "observables": ("the annual reserve-composition table",
                     "the monthly gold tonnage", "the reported profit or loss",
                     "the reserve headline in euro and in koruna"),
     "impact": "a central bank rebalancing a portfolio of this size into world equities is a "
               "real institutional flow, and the gold programme is a dated, disclosed, "
               "price-insensitive buyer in XAUUSD",
     "persistence": "the allocation persists for years; the gold ramp is a multi-year programme "
                    "with a stated target share",
     "falsifier": "months with disclosed gold purchases show no XAUUSD effect beyond the "
                  "aggregate central-bank buying already in the WGC series -- in which case "
                  "this is a WORLD flow and not a Czech one",
     "notes": "NO OTHER CENTRAL BANK ON THIS DESK hedges its reserves into equities at this "
              "scale; it is the single most distinctive institutional fact about Czechia"},
    {"name": "The Ministry of Finance debt desk (Odbor rizeni statniho dluhu)",
     "holds": "the domestic bond programme, the T-bill programme, the euro issuance and the "
              "state's cash position",
     "forced_to": ("publish a quarterly issuance calendar in advance",
                   "auction on that calendar and publish the results the same morning",
                   "publish the holder structure of the debt monthly",
                   "fund the deficit the budget act sets, at whatever the market charges"),
     "when": "auctions on the published calendar, most often midweek, results before noon local",
     "information": ("the primary dealers' indications before the auction",
                     "the cash position and the funding runway",
                     "the non-resident allocation before it is published"),
     "constraints": ("a calendar published a quarter ahead, which removes the surprise and "
                     "leaves only the OUTCOME as information",
                     "a retail bond programme that competes with its own wholesale issuance",
                     "an EU fiscal framework and a domestic debt brake"),
     "instruments": ("EURCZK", "USDCZK", "EURPLN"),
     "counterparties": ("the primary dealers", "the domestic pension and insurance books",
                        "the non-resident accounts whose share it publishes",
                        "the Czech household buying retail bonds"),
     "observables": ("the issuance calendar", "the auction cut-off and the bid-to-cover",
                     "the monthly holder structure", "the state's cash balance"),
     "impact": "a weak auction lifts the CZK curve and pressures EURCZK the same morning; a "
               "rising non-resident share is the foreign flow CZ-D conditions on",
     "persistence": "an auction effect is intraday to a few days; the holder-structure trend is "
                    "a multi-quarter state",
     "falsifier": "auction mornings are indistinguishable from the matched non-auction weekday "
                  "in the same week on EURCZK, in which case the supply event carries nothing",
     "notes": "one of very few packs on this desk where the supply calendar is KNOWN IN ADVANCE "
              "and the event can therefore be tested prospectively"},
    {"name": "The Czech Statistical Office (Cesky statisticky urad) as the release clock",
     "holds": "the CPI, GDP, industrial production, orders and trade prints, and the release "
              "calendar that dates every one of them",
     "forced_to": ("publish on a calendar announced a year in advance",
                   "release at 09:00 local, which is 08:00 or 07:00 UTC by season",
                   "revise on a published schedule rather than quietly",
                   "serve the data through a public queryable database"),
     "when": "09:00 Europe/Prague on the calendar date; CPI around the 10th-12th, industrial "
             "production about five weeks after the reference month",
     "information": ("the print before the market", "the revision before it is published",
                     "the methodology change before it lands"),
     "constraints": ("an EU statistical framework that fixes definitions and revision policy",
                     "a small open economy whose monthly series are noisy",
                     "a 2020 change in the external-trade concept that breaks the series"),
     "instruments": ("EURCZK", "USDCZK", "GER40"),
     "counterparties": ("Eurostat", "the CNB's forecasting staff",
                        "the bank research desks that publish the consensus"),
     "observables": ("the release calendar", "the print and its revision",
                     "the VDB machine-readable tables", "the methodological notes"),
     "impact": "the CPI print is the only Czech release with a published TARGET behind it, so "
               "it is the one whose surprise has a natural scale",
     "persistence": "a print's effect is intraday to a day; a methodology break is permanent",
     "falsifier": "the CPI window is indistinguishable from the same clock time on the "
                  "surrounding non-release days once the German prints are controlled for",
     "notes": "the 2020 trade-concept change is a series break this pack names so a study does "
              "not read it as an economic event"},
    {"name": "CEZ as the state-controlled power exporter",
     "holds": "the Czech nuclear and lignite fleet, the export position and the hedging "
              "programme that sells forward years ahead",
     "forced_to": ("declare outages on the REMIT and ENTSO-E transparency feed",
                   "sell into a COUPLED day-ahead market it does not set the price in",
                   "buy carbon allowances for every lignite megawatt-hour",
                   "publish results as a bond issuer and a majority-state-owned company"),
     "when": "outages are notified in advance and continuously; the day-ahead position clears "
             "at the 12:00 local gate every day",
     "information": ("its own outage and maintenance plan before the notice",
                     "the forward hedge ratio for the coming years",
                     "the fuel and carbon cost of its marginal plant"),
     "constraints": ("a coupled market: the price is set in Leipzig as much as in Prague",
                     "a carbon cost that is half the lignite plant's marginal cost",
                     "a state owner with a domestic price-cap agenda",
                     "nuclear availability that is lumpy and announced"),
     "instruments": ("XNGUSD", "XALUSD", "GER40"),
     "counterparties": ("the industrial offtakers including the aluminium and steel works",
                        "the German and Austrian buyers across the interconnector",
                        "the state as owner and as price regulator"),
     "observables": ("the ENTSO-E outage notices", "the OTE day-ahead clear and the CZ-DE "
                     "spread", "the CEPS cross-border physical flow",
                     "the disclosed hedge ratio"),
     "impact": "an announced nuclear outage flips the Czech marginal plant toward gas and widens "
               "the CZ-DE spread, which is the most direct physical XNGUSD trigger in this pack",
     "persistence": "an outage lasts days to weeks and is known in advance; the hedge ratio is "
                    "a multi-year state",
     "falsifier": "outage windows show no XNGUSD or CZ-DE spread effect beyond the German "
                  "fundamentals already in the price, in which case the Czech fleet is small "
                  "enough to be irrelevant to the coupled price",
     "notes": "AN ACTOR AND NEVER AN INSTRUMENT: the two-lane order (2026-09-06) forbids hunting "
              "the share statistically, and no share CFD appears anywhere in this pack"},
    {"name": "OTE a.s. as the day-ahead market operator and the coupling agent",
     "holds": "the Czech day-ahead and intraday auctions and the register of the coupled result",
     "forced_to": ("close the gate at 12:00 local every day without exception",
                   "clear jointly with the German, Austrian, Polish, Slovak and Hungarian zones",
                   "publish the hourly result within the hour",
                   "run the market on public holidays as well as working days"),
     "when": "12:00 Europe/Prague gate, results about 12:55 local, every calendar day",
     "information": ("the order book before the clear",
                     "the available cross-border capacity the TSOs submitted"),
     "constraints": ("SDAC rules set in Brussels rather than Prague",
                     "interconnector capacity that binds and decouples the zones on stressed "
                     "days", "a price cap and floor set at European level"),
     "instruments": ("XNGUSD", "XALUSD", "GER40"),
     "counterparties": ("the generators including the state fleet",
                        "the industrial consumers and the suppliers",
                        "the neighbouring zones' operators"),
     "observables": ("the hourly clearing price and volume", "the CZ-DE spread",
                     "the decoupling events when capacity binds",
                     "the intraday market's continuation"),
     "impact": "the 12:00 gate is the single moment the whole Central European power complex "
               "clears together, and the spread that survives it is the interconnector's "
               "binding constraint measured directly",
     "persistence": "a daily clear; the DECOUPLING state persists through a stressed week",
     "falsifier": "the CZ-DE spread carries no information about the next day's gas or "
                  "aluminium path beyond the German price itself",
     "notes": "the reason CZ-F is a coupling domain rather than a national power domain"},
    {"name": "The Energy Regulatory Office (Energeticky regulacni urad)",
     "holds": "the regulated distribution and system components of every Czech energy bill",
     "forced_to": ("publish a price decision each November for the following calendar year",
                   "publish it in the gazette, where it becomes citable",
                   "run the supplier-of-last-resort mechanism when a supplier fails",
                   "report on the market annually"),
     "when": "late November, for a 1 January effective date -- a dated administered price known "
             "five weeks in advance",
     "information": ("the network companies' cost base before the decision",
                     "the political tolerance for the size of the step"),
     "constraints": ("a statutory methodology it must follow",
                     "a government that has repeatedly capped or subsidised the price on top of "
                     "the regulated component",
                     "an obligation to publish rather than to negotiate"),
     "instruments": ("EURCZK", "XNGUSD", "USDCZK"),
     "counterparties": ("the distribution companies", "the suppliers and their customers",
                        "the Ministry of Industry and Trade"),
     "observables": ("the November price decision", "the gazette entry",
                     "the regulated component's weight in the CPI basket",
                     "the January CPI print it lands in"),
     "impact": "a known-in-advance step in January's CPI, which is the cleanest kind of "
               "administered inflation event a desk can test",
     "persistence": "a full calendar year by construction",
     "falsifier": "January CPI surprises are uncorrelated with the size of the November "
                  "decision, which would mean the market already prices it perfectly",
     "notes": "the one Czech inflation component whose date and size are both public before it "
              "happens"},
    {"name": "The Czech exporter treasury (the corporate forward book)",
     "holds": "EUR receivables from the German chain and a forward hedging programme against "
              "them, rolled at month ends",
     "forced_to": ("hedge a budgeted EUR revenue at a rate set by the parent's planning cycle",
                   "roll the book as contracts mature",
                   "stop hedging when a central bank floor makes hedging pointless",
                   "restart abruptly when the floor is removed"),
     "when": "clustered into the last and first business days of the month and into the "
             "budgeting season in the fourth quarter",
     "information": ("its own order book and the parent's production schedule",
                     "the hedge ratio across the whole sector, which nobody publishes live"),
     "constraints": ("a hedge ratio set by accounting policy rather than by a view",
                     "a parent company abroad that sets the budget rate",
                     "bank credit lines that cap the forward book's size"),
     "instruments": ("EURCZK", "USDCZK", "GER40"),
     "counterparties": ("the domestic banks that warehouse the forwards",
                        "the parent company's group treasury",
                        "the CNB, indirectly, as the ultimate counterparty at the floor"),
     "observables": ("the ARAD aggregate FX derivatives outstanding",
                     "the month-end EURCZK flow pattern",
                     "the banking sector's open FX position"),
     "impact": "the one recurring CZK flow that is not a policy act, and the reason the "
               "month-end window is a declared settlement convention in this pack",
     "persistence": "monthly, with an annual budgeting overlay",
     "falsifier": "the month-end EURCZK window matches the matched mid-month weekday control, "
                  "in which case there is no hedging clock here at all",
     "notes": "THE FLOOR CHANGED THIS ACTOR'S BEHAVIOUR: a guaranteed level removes the reason "
              "to hedge, so the post-2017 book had to be rebuilt -- a rare case where a policy "
              "regime visibly rewrote a private sector's flow"},
    {"name": "The offshore convergence account (the koruna carry club of 2015-2017)",
     "holds": "long-koruna positions put on at 27.00 against a central bank that had to fill "
              "them, funded in euro at a negative rate",
     "forced_to": ("accept the CNB's price while the commitment held",
                   "carry a position with a known floor and an unknown exit date",
                   "unwind into a market where everybody else was unwinding too"),
     "when": "accumulated 2015-2017 with the heaviest inflow in the final months before "
             "2017-04-06; the unwind ran for quarters afterwards",
     "information": ("its own size, which nobody outside it knew",
                     "the crowding, visible only in the reserve series and the holder structure"),
     "constraints": ("a position whose profit depended on a policy DECISION and not on a price",
                     "a funding cost that was negative and therefore nearly free",
                     "an exit that had no date and could not be hedged"),
     "instruments": ("EURCZK", "EURPLN", "EURHUF"),
     "counterparties": ("the CNB at the floor", "the domestic banks intermediating",
                        "each other, on the way out"),
     "observables": ("the reserve accumulation as the mirror of the position",
                     "the non-resident share of state debt",
                     "the forward points and the implied volatility",
                     "the slow post-exit grind rather than a gap"),
     "impact": "the exit produced NO GAP and a slow appreciation, which is itself the "
               "measurement: a crowded trade against a known counterparty unwinds into the same "
               "liquidity that created it",
     "persistence": "years to build, quarters to unwind",
     "falsifier": "the post-exit EURCZK path is explained entirely by the rate differential and "
                  "the euro-area tape, leaving no positioning residual at all",
     "notes": "CZ-D is a POSITIONING domain because of this actor, and the positioning series "
              "that measures it is a monthly official table, not a COT report that does not "
              "exist"},
    {"name": "The Czech commercial banks as the mortgage refixation channel",
     "holds": "a mortgage book fixed for three to five years, a large deposit base and the "
              "pricing of both",
     "forced_to": ("reprice a fixed mortgage only at its refixation date",
                   "pass a policy rate into deposits at a speed the competition sets",
                   "observe the CNB's LTV, DTI and DSTI limits",
                   "report the stock by fixation length to ARAD"),
     "when": "continuously, but the REFIXATION arrives three to five years after the loan was "
             "written, so the 2021-2022 hiking cycle reaches households in 2024-2027",
     "information": ("its own refixation schedule by month, years in advance",
                     "the deposit migration before the aggregate shows it"),
     "constraints": ("a fixed-rate book that cannot be repriced early",
                     "macroprudential limits that were tightened, suspended in 2020 and "
                     "restored", "a household that can and does move deposits to funds"),
     "instruments": ("EURCZK", "EUSTX50", "US500"),
     "counterparties": ("the Czech household", "the CNB as supervisor and as counterparty",
                        "the foreign parent groups that own most of the sector"),
     "observables": ("the Hypoindex average new rate", "the ARAD stock by fixation",
                     "the deposit-to-fund migration", "the CNB's limit decisions"),
     "impact": "the Czech tightening cycle is transmitted LATE and on a schedule that is "
               "knowable in advance -- a rare case where the lag is a published number",
     "persistence": "the refixation wave is a multi-year, dated flow",
     "falsifier": "consumption and the savings ratio show no step at the modelled refixation "
                  "peak, which would mean the channel is absorbed by incomes",
     "notes": "the difference from Poland is the whole point: a WIBOR-floating household "
              "repriced immediately and a Czech fixed one did not"},
    {"name": "The Czech household as saver, borrower and occasional euro buyer",
     "holds": "the deposit base, the retail state bonds and a growing fund and ETF allocation",
     "forced_to": ("choose between a term deposit, a retail state bond and a fund every time "
                   "the rate moves", "refix a mortgage on a date set years earlier",
                   "buy euro cash for holidays, which is a real seasonal retail flow"),
     "when": "the savings migration follows the rate with a lag of months; the euro cash demand "
             "is a summer and Christmas seasonal",
     "information": ("nothing the market does not have; this actor is a FOLLOWER and is "
                     "modelled as one",
                     "its own refixation date, which its bank told it years in advance"),
     "constraints": ("a deposit rate the banks set slowly",
                     "a retail bond programme the state switches on and off",
                     "ESMA leverage caps on any margin account"),
     "instruments": ("EURCZK", "EUSTX50", "XAUUSD"),
     "counterparties": ("the banks", "the robo-advisers and fund platforms",
                        "the state's retail bond desk"),
     "observables": ("the deposit and fund flow series in ARAD",
                     "the robo-advisers' published inflows",
                     "the retail bond subscription totals",
                     "the forum and search vocabulary at the turning points"),
     "impact": "small per household and large in aggregate; it is the demand side of CZ-I and "
               "the reason the retail-ecology layer is kept at all",
     "persistence": "a migration episode lasts quarters",
     "falsifier": "the fund and deposit flows are explained by the rate level alone with no "
                  "residual that the retail vocabulary dates",
     "notes": "kept at LOW WEIGHT and never a source of edge"},
    {"name": "The Prague Stock Exchange and the Central Securities Depository",
     "holds": "the PX index, the trading calendar, the settlement cycle and the turnover "
              "statistics",
     "forced_to": ("publish a trading calendar that follows the statutory holiday list",
                   "run a closing auction every session",
                   "settle T+2 through the CDCP",
                   "publish turnover and the foreign share monthly"),
     "when": "09:00-16:25 local continuous with a 16:20 closing call, every working day",
     "information": ("the closing auction's imbalance before the print",
                     "the member-level turnover before it is aggregated"),
     "constraints": ("a small free float dominated by banks and one utility",
                     "a dormant listed-derivatives market, so there is no expiry clock",
                     "foreign ownership concentrated in strategic rather than portfolio hands"),
     "instruments": ("EUSTX50", "GER40", "EURCZK"),
     "counterparties": ("the Vienna exchange group as owner",
                        "the domestic pension and fund books",
                        "the foreign brokers routing the flow"),
     "observables": ("the PX level and turnover", "the foreign turnover share",
                     "the closing auction print", "the dividend calendar"),
     "impact": "BOUNDED BY CONSTRUCTION: no PX CFD exists and the index is a handful of names, "
               "so CZ-K is a mechanics domain about the calendar and the settlement clock, "
               "never a return domain about the index",
     "persistence": "the microstructure facts persist for years",
     "falsifier": "the Czech session and settlement clock carries nothing for EUSTX50 or "
                  "EURCZK beyond the euro-area session itself",
     "notes": "the honest ceiling on this domain is stated rather than discovered later"},
    {"name": "The Skoda-Volkswagen subcontracting chain as an employer and an order book",
     "holds": "about a quarter of Czech goods exports and the largest single private employment "
              "cluster in the country, plus the tier-2 and tier-3 suppliers around it",
     "forced_to": ("follow a production schedule set in Wolfsburg rather than in Mlada "
                   "Boleslav", "shut a line when a German or Asian component does not arrive",
                   "report output monthly through the industry association",
                   "absorb an energy cost set in a coupled European market"),
     "when": "monthly production counts through AutoSAP; the shutdown and short-time events are "
             "announced and dated",
     "information": ("the order book and the model cycle before the market",
                     "the component shortages before the production number shows them"),
     "constraints": ("a parent's capital allocation decided abroad",
                     "the EU's emissions and tariff policy",
                     "a labour market with essentially no slack",
                     "Chinese competition in the parent's largest market"),
     "instruments": ("GER40", "EUSTX50", "EURCZK"),
     "counterparties": ("the German parent and its group treasury",
                        "the tier-2 suppliers across Czechia, Slovakia and Poland",
                        "the Czech state as an employer's counterparty and subsidy source"),
     "observables": ("AutoSAP monthly units", "the CSU vehicles line in industrial production",
                     "the German IFO and production prints",
                     "announced plant shutdowns and short-time working"),
     "impact": "this is the transmission CZ-E is about, and it reaches this desk as GER40 and "
               "EUSTX50 -- the INDEX, never the name",
     "persistence": "a model cycle is years; a shutdown is weeks",
     "falsifier": "Czech industrial production adds nothing to a German-production-based "
                  "forecast of GER40, which would make CZ-E a restatement of a German series",
     "notes": "AN ACTOR AND NEVER AN INSTRUMENT: no share CFD for any name in this cluster "
              "appears anywhere in this pack (two-lane order, 2026-09-06)"},
    {"name": "The European Commission as the EU funds paymaster",
     "holds": "the cohesion envelope and the Recovery and Resilience Facility tranches, and the "
              "decision of when they are paid",
     "forced_to": ("assess a payment request against published milestones",
                   "publish the decision", "pay in EUR, which the member state must convert",
                   "suspend when the conditionality it wrote is triggered"),
     "when": "irregular and dated; the payment requests and approvals cluster around quarter "
             "boundaries and around European Council meetings",
     "information": ("the assessment before it is published",
                     "the political negotiation behind the milestone"),
     "constraints": ("its own published rules and milestones",
                     "a Council that can and does overrule the technocratic reading",
                     "a member state that must co-finance and absorb"),
     "instruments": ("EURCZK", "EURPLN", "EURHUF"),
     "counterparties": ("the Czech Ministry of Regional Development and the Plan obnovy office",
                        "the other CEE member states competing for the same envelope",
                        "the Council"),
     "observables": ("the published payment decisions",
                     "the Czech payment requests and their dates",
                     "the NKU's audit findings on absorption",
                     "the state's EUR conversion around the receipt"),
     "impact": "a FORCED EUR-to-CZK conversion on a published date, which is the rarest kind of "
               "flow this desk gets: large, dated, and not a trade",
     "persistence": "a tranche is a one-off; the SUSPENSION regime persists for quarters and is "
                    "the shared mechanism with the Hungarian pack",
     "falsifier": "approval dates show no EURCZK effect once quarter-end and the euro tape are "
                  "controlled for, which would mean the conversion is smoothed away",
     "notes": "the interaction edge to the hu and pl packs lives here: one paymaster, three "
              "member states, and a conditionality switch that was pulled for two of them"},
)

# --------------------------------------------------------------------------- domains
#: Each domain carries `mechanism_family` and `horizon` beside the framework's four required
#: fields, because `cells()` mints one testable cell per (domain x instrument x condition) and a
#: cell with no family and no horizon is not a specification the gauntlet can run.
DOMAINS: tuple[dict[str, Any], ...] = (
    {"id": "CZ-A", "title": "The CNB decision at a fixed 14:30 local minute",
     "objects": ("the eight scheduled decisions a year and the vote split eight days later",
                 "the published forecast interest-rate path and its revision",
                 "the 2020 emergency cuts and the two extraordinary floor meetings",
                 "the bank research desks' published pre-meeting expectation"),
     "conditions": ("a forecast-round meeting (four a year, with a new Monetary Policy Report) "
                    "against an off-round one",
                    "the DST regime: the same local minute is 13:30 UTC in CET and 12:30 UTC "
                    "in CEST, and the two must never be pooled",
                    "the board's distance from its own published path at the meeting"),
     "instruments": ("EURCZK", "USDCZK", "EURPLN"),
     "controls": ("the same local-clock window on the four nearest non-meeting Thursdays",
                  "the same window on ECB decision days, separating 'the euro moved' from 'the "
                  "CNB decided'",
                  "EURPLN over the identical window as the CEE peer null"),
     "mechanism_family": "central_bank_surprise", "horizon": "intraday",
     "notes": "a FIXED announcement minute is rare on this desk; the only stamping work is the "
              "DST correction, which `decision_minute_utc` does"},
    {"id": "CZ-B", "title": "The EUR/CZK floor at 27.00 and the 2017 exit",
     "objects": ("the 2013-11-07 commitment and the 2017-04-06 abandonment",
                 "the truncated EURCZK distribution inside the era",
                 "the intervention volumes visible in the reserve series",
                 "the post-exit grind rather than a gap"),
     "conditions": ("inside the floor era against outside it -- the single most important "
                    "conditioning state in this pack",
                    "distance of the spot from 27.00 inside the era, which was a POLICY "
                    "distance and not a market one",
                    "the final six months before the exit, when the inflow accelerated"),
     "instruments": ("EURCZK", "EURPLN", "EURHUF"),
     "controls": ("EURPLN and EURHUF over the identical windows: the CEE peers had no floor, so "
                  "anything common to all three is a regional factor and not the commitment",
                  "the same statistics computed on a BLOCK-PERMUTED EURCZK series, which is the "
                  "null for a truncated distribution",
                  "the pre-2013 era, where the same state variable cannot vary"),
     "mechanism_family": "regime_break", "horizon": "multi_day",
     "notes": "WHAT THIS ERA INVALIDATES is enumerated in FLOOR_REGIME and must be carried into "
              "any study that spans it"},
    {"id": "CZ-C", "title": "The reserve pile, its equity tranche and the gold programme",
     "objects": ("the monthly reserve series and its floor-era step",
                 "the annual composition table and the equity share",
                 "the declared gold accumulation from 2024 and the monthly tonnage",
                 "the reported profit, loss and negative equity of the central bank"),
     "conditions": ("months with a disclosed gold purchase against months without",
                    "the rebalancing window implied by the annual composition disclosure",
                    "periods when the reported loss was politically live"),
     "instruments": ("XAUUSD", "US500", "EUSTX50"),
     "controls": ("the World Gold Council's aggregate central-bank purchase series, separating "
                  "'central banks bought gold' from 'the CNB bought gold'",
                  "matched months in the years before the 2024 programme began",
                  "a randomised-date null on the disclosure months"),
     "mechanism_family": "institutional_flow", "horizon": "multi_day",
     "notes": "no other central bank on this desk hedges reserves into equities at this scale; "
              "the flow is inferable from disclosure and never observable live"},
    {"id": "CZ-D", "title": "The koruna carry position and the non-resident share",
     "objects": ("the MF CR holder structure and its non-resident line",
                 "the PRIBOR-EURIBOR differential as the carry",
                 "the 2015-2017 accumulation and the post-exit unwind",
                 "the banking sector's open FX position in ARAD"),
     "conditions": ("the sign and size of the rate differential",
                    "the non-resident share's trend: rising, flat or falling",
                    "whether a floor or an intervention regime was in force"),
     "instruments": ("EURCZK", "EURPLN", "EURHUF"),
     "controls": ("the same carry state built on EURPLN, whose positioning is also unmeasured "
                  "by COT but whose differential is observable",
                  "the same windows with the differential SHUFFLED across months",
                  "the pre-2013 era, before the convergence trade existed"),
     "mechanism_family": "positioning", "horizon": "multi_day",
     "notes": "NO COT SERIES EXISTS FOR CZK. The positioning here is an official monthly table, "
              "which is slower and more honest than a proxy"},
    {"id": "CZ-E", "title": "The German automotive chain as an index transmission",
     "objects": ("AutoSAP monthly vehicle units",
                 "the CSU vehicles line inside industrial production",
                 "the German industrial production and orders prints at 08:00 CET",
                 "announced plant shutdowns and short-time working"),
     "conditions": ("the German print's own surprise on the same morning",
                    "months with an announced shutdown against months without",
                    "the model-cycle phase and the component-shortage regime"),
     "instruments": ("GER40", "EUSTX50", "EURCZK"),
     "controls": ("the German industrial production print itself as the dominant regressor: a "
                  "Czech number that adds nothing to it is a restatement",
                  "FRA40 and NETH25 over the same windows, separating 'European industry' from "
                  "'the German chain'",
                  "matched non-release weekdays at the same clock time"),
     "mechanism_family": "transfer", "horizon": "multi_day",
     "notes": "INDEX ONLY. Skoda and Volkswagen are actors; the two-lane order forbids hunting "
              "either statistically and no share CFD appears in this pack"},
    {"id": "CZ-F", "title": "The coupled day-ahead power market and the marginal plant",
     "objects": ("the OTE hourly day-ahead clear and the CZ-DE spread",
                 "CEPS cross-border physical flows and load",
                 "announced nuclear and lignite outages on the ENTSO-E feed",
                 "the decoupling days when interconnector capacity binds"),
     "conditions": ("an announced nuclear outage in force against a full fleet",
                    "a binding interconnector (decoupled zones) against a coupled clear",
                    "the load regime: a working day against a statutory holiday, which flattens "
                    "industrial demand and moves the marginal plant down the merit order"),
     "instruments": ("XNGUSD", "XALUSD", "GER40"),
     "controls": ("the German day-ahead price itself, separating 'Central European power' from "
                  "'Czech supply'",
                  "matched hours in weeks with no outage notice",
                  "a randomised-date null on the outage start dates"),
     "mechanism_family": "energy_complex", "horizon": "session",
     "notes": "power is not quoted here; the FUEL leg and the SMELTER leg are, and the day-ahead "
              "price is the input series"},
    {"id": "CZ-G", "title": "The MF CR auction calendar as a dated supply event",
     "objects": ("the quarterly issuance calendar published a quarter ahead",
                 "the auction cut-off yield and the bid-to-cover",
                 "the non-resident allocation",
                 "the retail state bond programme competing with the wholesale one"),
     "conditions": ("a heavy issuance quarter against a light one",
                    "an auction that fell in the same week as a CNB decision",
                    "the bid-to-cover relative to its own trailing distribution"),
     "instruments": ("EURCZK", "USDCZK", "EURPLN"),
     "controls": ("the matched non-auction weekday in the same week",
                  "Polish auction mornings over the same windows, separating 'CEE supply' from "
                  "'Czech supply'",
                  "weeks in which the calendar was published but no auction was held"),
     "mechanism_family": "calendar_settlement", "horizon": "session",
     "notes": "KNOWN IN ADVANCE, which makes this one of the few prospectively testable event "
              "clocks on the whole desk"},
    {"id": "CZ-H", "title": "The CSU release clock and the 09:00 local print",
     "objects": ("the CPI, GDP flash, industrial production and trade prints",
                 "the published release calendar a year ahead",
                 "the revision schedule and the 2020 trade-concept break",
                 "the bank desks' published consensus"),
     "conditions": ("the release type: an inflation print with a published target behind it "
                    "against an activity print with none",
                    "whether a German print landed at 08:00 CET the same morning",
                    "the DST regime, which moves the 09:00 local print between 08:00 and 07:00 "
                    "UTC"),
     "instruments": ("EURCZK", "USDCZK", "GER40"),
     "controls": ("matched non-release weekdays at the same LOCAL clock time",
                  "the German print at 08:00 CET as the competing explanation",
                  "the same windows across the 2020 methodology break, which must be split"),
     "mechanism_family": "release_surprise", "horizon": "intraday",
     "notes": "the CPI is the only Czech release with a published target, so its surprise has a "
              "natural scale the activity prints do not"},
    {"id": "CZ-I", "title": "The fixed-rate mortgage refixation wave",
     "objects": ("the ARAD loan stock by fixation length",
                 "the Hypoindex average new-mortgage rate",
                 "the CNB's LTV, DTI and DSTI decisions, including the 2020 suspension",
                 "the household deposit-to-fund migration"),
     "conditions": ("the modelled refixation volume in the month, derived from the stock by "
                    "fixation and the origination vintage",
                    "whether a macroprudential limit was in force, suspended or restored",
                    "the deposit-rate gap to the policy rate"),
     "instruments": ("EURCZK", "EUSTX50", "US500"),
     "controls": ("Poland's floating-rate household over the same cycle, which repriced "
                  "immediately: the difference IS the mechanism",
                  "months with no modelled refixation peak",
                  "the same series through the 2020 suspension, which must be split"),
     "mechanism_family": "credit_channel", "horizon": "multi_day",
     "notes": "the lag here is a PUBLISHED number -- the fixation length -- which is rare"},
    {"id": "CZ-J", "title": "EU funds as a dated, forced EUR-to-CZK conversion",
     "objects": ("the Commission's payment decisions and the Czech payment requests",
                 "the Narodni plan obnovy milestone calendar",
                 "the NKU's absorption audits",
                 "the quarter-end clustering of the conversions"),
     "conditions": ("an approved tranche in the quarter against none",
                    "the size of the tranche relative to monthly FX turnover",
                    "whether the same quarter carried a Polish or Hungarian suspension event, "
                    "which moves the whole CEE complex"),
     "instruments": ("EURCZK", "EURPLN", "EURHUF"),
     "controls": ("quarter-end windows in quarters with no tranche",
                  "EURPLN over the identical windows, since Poland receives from the same "
                  "paymaster on a different schedule",
                  "a randomised-date null on the approval dates"),
     "mechanism_family": "forced_flow", "horizon": "multi_day",
     "notes": "large, dated and not a trade, which is the rarest shape of flow this desk sees"},
    {"id": "CZ-K", "title": "Prague session mechanics, settlement and the holiday clock",
     "objects": ("the PSE trading calendar derived from the statute",
                 "the closing auction at 16:20-16:25 local",
                 "T+2 settlement at the CDCP and the month-end cluster",
                 "the foreign turnover share"),
     "conditions": ("a Czech statutory holiday when the euro-area market is open -- a "
                    "single-country closure, which is the interesting case",
                    "a LOST weekend holiday, when no session is closed at all despite the "
                    "statute naming the day",
                    "the DST regime, which moves the whole Prague session an hour in UTC"),
     "instruments": ("EUSTX50", "GER40", "EURCZK"),
     "controls": ("the same weekdays when Prague was open and Frankfurt closed, the mirror case",
                  "matched weekdays 26 weeks away on the same clock",
                  "the euro-area session's own volume profile as the dominant explanation"),
     "mechanism_family": "session_microstructure", "horizon": "session",
     "notes": "BOUNDED BY CONSTRUCTION: no PX CFD exists, so this is a mechanics domain about "
              "the calendar and never a return domain about the index"},
    {"id": "CZ-L", "title": "The statutory calendar, the lost weekend holidays and DST",
     "objects": ("the eleven fixed statutory days and the two Easter-derived ones",
                 "Good Friday's arrival in 2016 as a new closed day",
                 "the holidays that fall at the weekend and are LOST with no substitute",
                 "the CET/CEST boundary and the 14:30-local announcement's UTC drift"),
     "conditions": ("a closed session against a lost weekend holiday against a normal weekday",
                    "the bridge configuration: a holiday on a Tuesday or Thursday, which "
                    "empties the adjacent working day in practice without closing it",
                    "CET against CEST"),
     "instruments": ("EURCZK", "EUSTX50", "GER40"),
     "controls": ("matched weekdays 26 weeks away, the desk's standard holiday control",
                  "German statutory holidays over the same windows, separating 'Central Europe "
                  "is closed' from 'Czechia is closed'",
                  "the pre-2016 Good Fridays, when the day was a normal session"),
     "mechanism_family": "holiday_liquidity", "horizon": "session",
     "notes": "the number of closed SESSIONS varies by up to four days a year on the calendar "
              "alone, which a naive closed-day count gets wrong in both directions"},
    {"id": "CZ-M", "title": "The regulated energy price and the January inflation step",
     "objects": ("the ERU November price decision for the following year",
                 "the government caps and subsidy schemes layered on top of it",
                 "the regulated component's weight in the CPI basket",
                 "the January CPI print it lands in"),
     "conditions": ("the size of the November decision relative to its own history",
                    "whether a government cap or subsidy was also in force",
                    "the level of the OTE day-ahead price the decision was set against"),
     "instruments": ("EURCZK", "XNGUSD", "USDCZK"),
     "controls": ("January prints in years with a small or zero regulated step",
                  "the non-regulated CPI components over the same months as the internal "
                  "placebo",
                  "German and Polish regulated-energy steps in the same January"),
     "mechanism_family": "administered_price", "horizon": "multi_day",
     "notes": "date and size are BOTH public five weeks before the print, which is the cleanest "
              "administered-inflation event this desk can test"},
)

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "cz_cnb_decision_windows", "domain_ids": ("CZ-A",), "kind": "event",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.cz.miners:cnb_decision_windows",
     "needs": ("CENTRAL_BANK decision dates", "EURCZK, USDCZK, EURPLN H1 bars"),
     "notes": "the fixed 14:30 local minute, split by DST regime rather than pooled"},
    {"name": "cz_floor_regime_break", "domain_ids": ("CZ-B", "CZ-D"), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.cz.miners:floor_regime_break",
     "needs": ("FLOOR_REGIME", "EURCZK, EURPLN, EURHUF D1 bars"),
     "notes": "the two dates as regime boundaries with the CEE peers as the concurrent null"},
    {"name": "cz_auction_calendar", "domain_ids": ("CZ-G",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.cz.miners:auction_calendar",
     "needs": ("the MF CR midweek auction clock", "EURCZK H1 bars"),
     "notes": "the matched non-auction weekday placebo is built in, because a midweek effect is "
              "a weekday effect until it is told apart from one"},
    {"name": "cz_holiday_session_clock", "domain_ids": ("CZ-L", "CZ-K"), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.cz.miners:holiday_session_clock",
     "needs": ("national_holidays", "EURCZK, EUSTX50, GER40 H1 bars"),
     "notes": "single-country closures and LOST weekend holidays as two different states"},
    {"name": "cz_power_outage_fuel", "domain_ids": ("CZ-F", "CZ-M"), "kind": "macro",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.cz.miners:power_outage_fuel",
     "needs": ("OTE:DA_price_CZ", "XNGUSD, XALUSD D1 bars"),
     "notes": "the day-ahead price as a dated lead into the fuel and smelter legs"},
    {"name": "cz_transmission_seeds",
     "domain_ids": ("CZ-C", "CZ-E", "CZ-I", "CZ-J", "CZ-H"), "kind": "transfer",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.cz.miners:transmission_seeds",
     "needs": ("TRANSMISSION_EDGES_SEED",),
     "notes": "the pack's map as HYPOTHESIS discoveries, deduplicated by the registry"},
)
MINER_DOMAINS: dict[str, tuple[str, ...]] = {
    "central_bank_surprise": ("CZ-A",), "release_surprise": ("CZ-H", "CZ-M"),
    "calendar_settlement": ("CZ-G", "CZ-K"), "holiday_liquidity": ("CZ-L",),
    "positioning": ("CZ-D",), "carry_funding": ("CZ-D", "CZ-A"),
    "corporate_flow": ("CZ-E", "CZ-I"), "institutional_flow": ("CZ-C", "CZ-J"),
    "equity_mechanics": ("CZ-K",), "derivatives_expiry": ("CZ-K",),
    "failure": ("CZ-B", "CZ-F"), "residual": ("CZ-B", "CZ-D"),
    "transfer": ("CZ-E", "CZ-F"), "scouts": ("CZ-J", "CZ-M"),
    "session_microstructure": ("CZ-K", "CZ-L"),
}

# --------------------------------------------------------------------------- transmission
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"id": "CZ-T1", "source": "The CNB's fixed 14:30 local policy decision",
     "target": "EURCZK", "targets": ("EURCZK", "USDCZK"), "to_country": "cz", "sign": "-",
     "mechanism": "a rate surprise against the bank's own published path repriced into the "
                  "whole koruna curve within minutes; the currency leg is directly executable, "
                  "so this is a cell and not a proxy",
     "horizon": "intraday", "horizon_class": "intraday", "lag_days": 0.0,
     "actor": "the bankovni rada", "constraint": "eight decisions a year and a published path",
     "flow": "rate repricing", "condition": "a forecast-round meeting, split by DST regime",
     "control": "the four nearest non-meeting Thursdays at the same LOCAL clock; ECB decision "
                "days over the same window",
     "falsifier": "the decision window is indistinguishable from the matched Thursday once "
                  "EURUSD is controlled for", "evidence": "HYPOTHESIS"},
    {"id": "CZ-T2", "source": "The 2013-11-07 floor commitment and the 2017-04-06 exit",
     "target": "EURCZK", "targets": ("EURCZK", "EURPLN", "EURHUF"), "to_country": "cz",
     "sign": "+",
     "mechanism": "an administratively truncated distribution: inside the era EURCZK's downside "
                  "did not exist, so realised volatility, carry and momentum were policy "
                  "choices rather than market outcomes",
     "horizon": "years, with two dated boundaries", "horizon_class": "multi_day",
     "lag_days": 0.0, "actor": "the CNB FX desk",
     "constraint": "a ONE-SIDED commitment: a floor under EUR/CZK and never a ceiling",
     "flow": "unlimited intervention", "condition": "inside the era against outside it",
     "control": "EURPLN and EURHUF over the identical windows; a block-permuted EURCZK series",
     "falsifier": "the era's EURCZK distribution matches the surrounding years' once the pin is "
                  "removed", "evidence": "MEASURED_ELSEWHERE"},
    {"id": "CZ-T3", "source": "The CNB's declared gold accumulation programme",
     "target": "XAUUSD", "targets": ("XAUUSD",), "to_country": "global", "sign": "+",
     "mechanism": "a disclosed, price-insensitive official buyer adding to a multi-year target "
                  "share of reserves; the purchases are reported monthly and the programme has "
                  "a stated destination rather than a tactical view",
     "horizon": "1 to 3 months", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the CNB reserve management division",
     "constraint": "the flow is disclosed AFTER the month, so it is a conditioner and never a "
                   "trigger", "flow": "official gold purchase",
     "condition": "months with a disclosed purchase above the programme's own median",
     "control": "the World Gold Council aggregate central-bank purchase series over the same "
                "months; matched months before the programme began",
     "falsifier": "disclosed Czech purchase months show no XAUUSD effect beyond the aggregate "
                  "official-sector series", "evidence": "HYPOTHESIS"},
    {"id": "CZ-T4", "source": "The CNB reserve portfolio's global equity tranche",
     "target": "US500", "targets": ("US500", "EUSTX50"), "to_country": "global", "sign": "+",
     "mechanism": "a reserve pile the size of the economy, part of it benchmarked to world "
                  "equity indices, must be rebalanced back to target weights after a large "
                  "move -- a mechanical, size-dependent institutional flow",
     "horizon": "quarterly", "horizon_class": "multi_day", "lag_days": 90.0,
     "actor": "the CNB reserve management division",
     "constraint": "the composition is disclosed ANNUALLY, so the rebalancing window is "
                   "inferred and the claim says so",
     "flow": "index rebalancing", "condition": "quarters following a large drawdown or rally",
     "control": "the same windows for reserve managers with no equity tranche; a randomised "
                "quarter null",
     "falsifier": "no rebalancing residual survives once the global index calendar is "
                  "controlled for", "evidence": "HYPOTHESIS"},
    {"id": "CZ-T5", "source": "Czech industrial production and AutoSAP vehicle units",
     "target": "GER40", "targets": ("GER40", "EUSTX50"), "to_country": "de", "sign": "+",
     "mechanism": "the Czech plant is a subcontracted limb of the German automotive chain, so "
                  "its output count is a same-cycle read on the chain that the German print "
                  "itself is the primary measure of",
     "horizon": "1 to 2 months", "horizon_class": "multi_day", "lag_days": 12.0,
     "actor": "the Skoda-Volkswagen supplier cluster",
     "constraint": "the schedule is set in Wolfsburg, so this is a DERIVED series and the claim "
                   "must beat the German print to mean anything",
     "flow": "order book into output",
     "condition": "months where the AutoSAP count diverges from the German production print",
     "control": "German industrial production as the dominant regressor; FRA40 and NETH25 over "
                "the same windows",
     "falsifier": "the Czech series adds nothing to a German-production-based forecast of "
                  "GER40", "evidence": "HYPOTHESIS"},
    {"id": "CZ-T6", "source": "An announced Czech nuclear outage on the ENTSO-E feed",
     "target": "XNGUSD", "targets": ("XNGUSD", "XALUSD"), "to_country": "global", "sign": "+",
     "mechanism": "losing a nuclear block moves the Czech marginal plant down the merit order "
                  "toward gas and widens the CZ-DE day-ahead spread, which raises the gas call "
                  "and the smelter's input cost inside a coupled market",
     "horizon": "days to weeks", "horizon_class": "multi_day", "lag_days": 1.0,
     "actor": "CEZ and the grid operator",
     "constraint": "the notice is PUBLISHED IN ADVANCE, so the event is anticipated and the "
                   "test must use the notice date and not the outage date",
     "flow": "physical supply loss",
     "condition": "an outage notice covering more than a declared share of the fleet",
     "control": "the German day-ahead price itself; matched hours in weeks with no notice",
     "falsifier": "outage windows carry no XNGUSD or spread effect beyond German fundamentals",
     "evidence": "HYPOTHESIS"},
    {"id": "CZ-T7", "source": "The ERU November regulated-price decision",
     "target": "EURCZK", "targets": ("EURCZK", "USDCZK"), "to_country": "cz", "sign": "-",
     "mechanism": "a dated administered step that enters January's CPI mechanically; the size "
                  "is public five weeks before the print, so the CPI surprise is decomposable "
                  "into a known administered part and an unknown market part",
     "horizon": "the January print", "horizon_class": "multi_day", "lag_days": 45.0,
     "actor": "the Energy Regulatory Office",
     "constraint": "the decision is published, so only the market's FAILURE to price it can "
                   "carry a return",
     "flow": "administered price into CPI",
     "condition": "years with a large regulated step against years with a small one",
     "control": "the non-regulated CPI components as an internal placebo; German and Polish "
                "regulated steps in the same January",
     "falsifier": "January CPI surprises are uncorrelated with the size of the November "
                  "decision", "evidence": "HYPOTHESIS"},
    {"id": "CZ-T8", "source": "The MF CR midweek government bond auction",
     "target": "EURCZK", "targets": ("EURCZK", "USDCZK"), "to_country": "cz", "sign": "-",
     "mechanism": "a dated forced-supply event whose calendar is published a quarter ahead, so "
                  "the surprise is entirely in the OUTCOME -- the cut-off and the bid-to-cover "
                  "against their own trailing distribution",
     "horizon": "intraday to two days", "horizon_class": "session", "lag_days": 0.0,
     "actor": "the Ministry of Finance debt desk",
     "constraint": "a published calendar removes the timing surprise and leaves only the result",
     "flow": "primary supply",
     "condition": "a bid-to-cover in the lower tail of its own trailing distribution",
     "control": "the matched non-auction weekday in the same week; Polish auction mornings",
     "falsifier": "auction mornings match the matched weekday on EURCZK",
     "evidence": "HYPOTHESIS"},
    {"id": "CZ-T9", "source": "An approved EU cohesion or RRF tranche for Czechia",
     "target": "EURCZK", "targets": ("EURCZK", "EURPLN"), "to_country": "cz", "sign": "-",
     "mechanism": "a large EUR receipt the state must convert into koruna on a schedule set in "
                  "Brussels: a forced flow, dated by a published decision, with no trading "
                  "motive behind it at all",
     "horizon": "days around the approval and the quarter end", "horizon_class": "multi_day",
     "lag_days": 5.0, "actor": "the European Commission and the Czech treasury",
     "constraint": "the conversion may be smoothed by the treasury, which would hide the flow",
     "flow": "forced EUR-to-CZK conversion",
     "condition": "a tranche whose size is large relative to monthly FX turnover",
     "control": "quarter-end windows in quarters with no tranche; EURPLN over the same windows",
     "falsifier": "approval dates carry no EURCZK effect once quarter-end is controlled for",
     "evidence": "HYPOTHESIS"},
    {"id": "CZ-T10", "source": "A Czech statutory holiday that closes Prague while the euro "
                               "area trades",
     "target": "EURCZK", "targets": ("EURCZK", "EUSTX50"), "to_country": "cz", "sign": "+",
     "mechanism": "a single-country closure removes the domestic market maker and the local "
                  "corporate flow while the euro-area tape runs, which thins the koruna leg "
                  "without thinning its counterpart",
     "horizon": "the session", "horizon_class": "session", "lag_days": 0.0,
     "actor": "the statute and the exchange calendar",
     "constraint": "only the weekday holidays matter; the LOST weekend ones close nothing",
     "flow": "liquidity withdrawal",
     "condition": "a Czech weekday holiday when Frankfurt is open",
     "control": "matched weekdays 26 weeks away; German holidays when Prague is open",
     "falsifier": "single-country closure days match the matched control on every spread and "
                  "range measure", "evidence": "HYPOTHESIS"},
    {"id": "CZ-T11", "source": "The PRIBOR-EURIBOR differential and the non-resident share of "
                               "Czech state debt",
     "target": "EURCZK", "targets": ("EURCZK", "EURPLN", "EURHUF"), "to_country": "cz",
     "sign": "-",
     "mechanism": "the carry a koruna position earns, together with the only published measure "
                  "of who is holding it; a crowded carry unwinds into the same liquidity that "
                  "built it, which is what the 2017 exit demonstrated without a gap",
     "horizon": "1 to 2 quarters", "horizon_class": "multi_day", "lag_days": 30.0,
     "actor": "the offshore convergence account",
     "constraint": "NO COT SERIES EXISTS FOR CZK, so positioning is a monthly official table "
                   "and every claim here is slower than a weekly one would be",
     "flow": "carry accumulation and unwind",
     "condition": "a rising non-resident share with a positive differential",
     "control": "the same state on EURPLN; a shuffled differential across months",
     "falsifier": "the post-exit EURCZK path is fully explained by the differential and the "
                  "euro-area tape with no positioning residual",
     "evidence": "HYPOTHESIS"},
)

#: INTERACTION MINERS -- the other country packs this one has a MEASURABLE interaction with.
#: A desk that tests each country in isolation tests the same shared driver once per country and
#: charges the trial budget for all of them; these rows are where the shared driver is named.
INTERACTIONS: tuple[dict[str, Any], ...] = (
    {"with": "pl",
     "mechanism": "the CEE convergence complex: two floating CEE currencies with two different "
                  "central banks, two different mortgage contracts (Czech fixed, Polish "
                  "floating) and one shared German industrial driver. Anything common to "
                  "EURCZK and EURPLN is the regional factor; the RESIDUAL is the country",
     "observable": "the EURCZK/EURPLN correlation and its regime dependence; the PRIBOR-WIBOR "
                   "differential; the two auction calendars in the same week",
     "targets": ("EURCZK", "EURPLN", "GER40"),
     "control": "the German industrial print and EURUSD, which are the two things both "
                "currencies are exposed to before either is exposed to the other"},
    {"with": "hu",
     "mechanism": "the EU funds conditionality switch: one paymaster, three member states, and "
                  "a rule-of-law suspension that was pulled for Hungary and Poland and never "
                  "for Czechia. A Hungarian suspension or release moves the whole CEE complex, "
                  "and Czechia is the leg with no political discount in it -- which makes it "
                  "the CLEAN CONTROL for every Hungarian political event",
     "observable": "EURCZK on Hungarian conditionality decision dates; the EURHUF/EURCZK spread "
                   "around Council and Commission decisions",
     "targets": ("EURCZK", "EURHUF", "EURPLN"),
     "control": "Czech-specific events in the same windows, and the euro-area tape"},
    {"with": "ea",
     "mechanism": "the German automotive chain and the ECB's own decision clock. Czech industry "
                  "is a subcontracted limb of German industry, and the CNB decides fifteen days "
                  "either side of the ECB with a published path of its own -- so a Czech "
                  "decision-day effect that coincides with an ECB day is a euro event until "
                  "proven otherwise",
     "observable": "GER40 and EUSTX50 around Czech prints; the CNB-ECB rate differential; the "
                   "08:00 CET German release window",
     "targets": ("GER40", "EUSTX50", "EURCZK"),
     "control": "ECB decision days and German release days as the competing explanation"},
    {"with": "ru",
     "mechanism": "the energy severance. Czechia replaced Russian pipeline gas and is "
                  "diversifying its nuclear fuel supply, so the Central European power price "
                  "and the gas call carry a Russian-supply term that did not exist before 2022 "
                  "and is now a dated policy state rather than a market one",
     "observable": "the CZ-DE day-ahead spread and the gas call through a supply-interruption "
                   "episode; the Czech LNG regasification booking",
     "targets": ("XNGUSD", "XALUSD", "GER40"),
     "control": "the German and Austrian zones over the same episodes, and the TTF benchmark"},
    {"with": "uk",
     "mechanism": "the non-euro European rate complex. The CNB, the Bank of England and the "
                  "Riksbank are the three developed non-euro European central banks whose "
                  "decisions are read against the ECB's; a Czech decision that moves EURCZK "
                  "the same way a BoE decision moves EURGBP is a EUROPEAN RATE factor, not a "
                  "Czech one",
     "observable": "the co-movement of EURCZK and the euro-sterling leg around the two "
                   "decision clocks; the shared response to euro-area inflation prints",
     "targets": ("EURCZK", "EURUSD", "EUSTX50"),
     "control": "EURUSD as the common euro leg, and non-decision weekdays in both calendars"},
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "inflation targeting at the lower bound", "start": "2010-01-01",
     "end": "2013-11-06",
     "regime": "a 2% target with a +/-1pp band from 2010-01; the 2W repo rate driven to its "
               "technical zero of 0.05% in November 2012 and held there, leaving the board with "
               "no conventional instrument at all",
     "markers": ("2010-01 the 2% target takes effect",
                 "2012-11 the repo rate reaches its technical zero"),
     "why_it_matters": "the era that CREATED the floor: with the rate instrument exhausted, the "
                       "exchange rate was the only lever left, which is why CZ-B is a monetary "
                       "domain and not an FX-intervention curiosity",
     "status": "SETTLED"},
    {"name": "the EUR/CZK floor at 27.00", "start": "2013-11-07", "end": "2017-04-05",
     "regime": "an unlimited one-sided commitment to keep EUR/CZK at or above 27.00, repeated "
               "at every meeting; reserves grew from roughly a third of GDP to more than "
               "two-thirds paying for it",
     "markers": ("2013-11-07 the commitment announced at an extraordinary meeting",
                 "2015-2016 the offshore convergence trade builds",
                 "2017-Q1 the inflow accelerates as the exit is anticipated"),
     "why_it_matters": "EVERY EURCZK VOLATILITY, TAIL, CARRY AND MOMENTUM STATISTIC estimated "
                       "across this boundary is estimated on two different random variables "
                       "glued together; the downside of the distribution was administratively "
                       "removed and the pack says so in FLOOR_REGIME",
     "status": "SETTLED"},
    {"name": "the exit and the carry unwind", "start": "2017-04-06", "end": "2019-12-31",
     "regime": "the commitment abandoned on 2017-04-06 with no gap and a slow appreciation; a "
               "conventional hiking cycle followed from August 2017 while the crowded long "
               "position unwound over quarters",
     "markers": ("2017-04-06 the floor abandoned",
                 "2017-08 the first conventional hike in years",
                 "2018-2019 the non-resident share of state debt falls back"),
     "why_it_matters": "the cleanest available natural experiment in crowded-position unwind: "
                       "everybody knew the counterparty, everybody knew the level, and the exit "
                       "still produced no gap",
     "status": "SETTLED"},
    {"name": "the pandemic cuts", "start": "2020-01-01", "end": "2021-06-22",
     "regime": "emergency cuts on 2020-03-16 and 2020-03-26 took the rate to 0.25%; the "
               "macroprudential LTV/DTI/DSTI limits were SUSPENDED, which is a second regime "
               "break inside the mortgage channel",
     "markers": ("2020-03-16 and 2020-03-26 the emergency cuts",
                 "2020-04 the macroprudential limits suspended",
                 "2020-2021 the mortgage origination boom that becomes the refixation wave"),
     "why_it_matters": "the loans written here at record-low fixed rates are exactly the stock "
                       "that refixes in 2024-2027, so this era is the SOURCE of CZ-I's dated "
                       "future flow",
     "status": "SETTLED"},
    {"name": "the hiking cycle to 7.00%", "start": "2021-06-23", "end": "2022-06-30",
     "regime": "eight consecutive hikes took the 2W repo rate from 0.25% to 7.00% -- among the "
               "fastest tightening cycles in the developed world -- while the board debated "
               "using the exchange rate again",
     "markers": ("2021-06-23 the first hike", "2021-11-04 a 125bp step",
                 "2022-06-22 the last hike of the cycle at 7.00%"),
     "why_it_matters": "the only modern Czech hiking sample and it is eight decisions long; a "
                       "study that needs more events than that must say so rather than pool it "
                       "with the easing cycle",
     "status": "SETTLED"},
    {"name": "the Michl board: the 7.00% plateau and the strong-koruna regime",
     "start": "2022-07-01", "end": "2023-12-20",
     "regime": "a new governor and a reshaped board held the rate at 7.00% for eighteen months "
               "and defended the koruna directly with FX sales rather than with further hikes; "
               "the gold accumulation programme was set out in this period",
     "markers": ("2022-07-01 the new board takes office",
                 "2022-H2 open FX sales to support the koruna",
                 "2023 the gold programme announced"),
     "why_it_matters": "a HOLD regime with an ACTIVE FX policy is a different data-generating "
                       "process from either a hiking cycle or a floor, and it is the era where "
                       "the CNB's reserve strategy became a market fact in its own right",
     "status": "SETTLED"},
    {"name": "the easing cycle and the refixation wave", "start": "2023-12-21",
     "end": "2026-12-31",
     "regime": "cuts from 2023-12-21 onward walked the rate back down through 2024 and 2025 "
               "while the 2020-2021 mortgage vintage began to refix at higher rates and the "
               "gold tranche kept growing",
     "markers": ("2023-12-21 the first cut", "2024 the eight-meeting easing sequence",
                 "2024-2027 the refixation wave arrives at households"),
     "why_it_matters": "the current regime; the decision sample here is cuts and holds only, "
                       "and the household channel is finally transmitting the 2021-22 cycle",
     "status": "OPEN"},
)

ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "the koruna IS quoted by this broker, which is the opposite of most packs",
     "measured": "EURCZK and USDCZK are both in data/universe/universe.json",
     "consequence": "almost every domestic mechanism in this pack terminates in a DIRECTLY "
                    "EXECUTABLE symbol, which is why its cell count is high and its "
                    "transmission-target list is short"},
    {"constraint": "no COT or exchange positioning series exists for CZK",
     "measured": "no koruna future trades on any exchange the desk reads",
     "consequence": "CZ-D's positioning is the MF CR monthly holder structure, which is slower "
                    "and coarser than a weekly COT and is never proxied by the EUR COT leg"},
    {"constraint": "the CNB reserve COMPOSITION is annual, not monthly",
     "measured": "the headline reserve number is monthly; the equity share and the currency "
                 "split appear only in the annual report",
     "consequence": "CZ-C's equity-tranche claims are annual conditioners; a monthly "
                    "rebalancing claim would be inferring a flow from a number published once "
                    "a year, and the pack refuses to"},
    {"constraint": "the forward power and carbon curves forbid machine extraction",
     "measured": "ICIS, Argus and Montel terms; registered machine_use_allowed=false",
     "consequence": "CZ-F is measured on the OTE day-ahead print, which is free, and on the "
                    "executable fuel and smelter legs -- never on a licensed forward curve"},
    {"constraint": "the ERU, OTE and MF CR pages overwrite in place",
     "measured": "each shows the CURRENT decision, price or calendar and keeps no vintage",
     "consequence": "the point-in-time reconstruction of what was KNOWN on a date exists only "
                    "in the archive layer's crawls; a cell compiled on an un-archived month is "
                    "UNMEASURED rather than assumed"},
    {"constraint": "the CNB decision calendar for 2026 is not carried here",
     "measured": "CENTRAL_BANK['decision_dates'] stops in 2025 and dates_status says so",
     "consequence": "CZ-A cells for 2026 are UNMEASURED until the published calendar is read; "
                    "the pack refuses to invent a decision date (L1.28a)"},
    {"constraint": "no PX CFD and no listed Czech index derivative exist",
     "measured": "the broker registry holds no PX symbol and the PSE derivatives market is "
                 "dormant",
     "consequence": "CZ-K is a MECHANICS domain about the calendar and the settlement clock; "
                    "there is no expiry effect to mine and the pack says so rather than "
                    "manufacturing one"},
)
INSTITUTIONAL_FLOW_SOURCES: tuple[str, ...] = (
    "MF CR monthly holder structure of state debt (the non-resident share)",
    "CNB monthly foreign exchange reserves and the annual composition table",
    "CNB ARAD banking-sector open FX position and FX derivatives outstanding",
    "PSE monthly foreign turnover share", "AutoSAP monthly vehicle production",
    "European Commission RRF and cohesion payment decisions for Czechia")
SERIES: dict[str, str] = {
    "CZ_POLICY": "CNB:2T_repo_sazba", "CZ_FX_FIXING": "CNB:kurz_EURCZK",
    "CZ_RESERVES": "CNB:reserves", "CZ_GOLD": "CNB:gold_tonnes",
    "CZ_CPI": "CZSO:CPI", "CZ_IP": "CZSO:industrial_production",
    "CZ_TRADE_DE": "CZSO:trade_de", "CZ_GDP": "CZSO:GDP_flash",
    "CZ_AUCTION": "MFCR:auction_yield", "CZ_NONRESIDENT": "MFCR:nonresident_share",
    "CZ_POWER_DA": "OTE:DA_price_CZ", "CZ_PRIBOR": "CFBF:PRIBOR_3M",
    "CZ_MORTGAGE": "HYPOINDEX:avg_rate", "CZ_REGULATED": "ERU:regulated_component",
}


# --------------------------------------------------------------------------- mechanism fns
def floor_era_days(start: date, end: date) -> list[date]:
    """Every WEEKDAY inside the EUR/CZK floor era that also falls inside [start, end].

    THE POINT OF THIS FUNCTION. Every EURCZK statistic this desk computes has to know whether
    the day it is standing on was inside an administratively truncated distribution. A study
    that pools 2013-11-07..2017-04-06 with the surrounding years is not estimating one random
    variable, and this is the mask that stops it.
    """
    lo = max(start, FLOOR_REGIME["announced"])
    hi = min(end, FLOOR_REGIME["exited"])
    out: list[date] = []
    cur = lo
    while cur < hi:
        if cur.weekday() < 5:
            out.append(cur)
        cur += timedelta(days=1)
    return out


def in_floor_era(day: date) -> bool:
    """True when a date sits inside the floor commitment (inclusive of the announcement day,
    exclusive of the exit day, which is itself the regime-break event)."""
    return bool(FLOOR_REGIME["announced"] <= day < FLOOR_REGIME["exited"])


def single_country_closures(year: int) -> dict[date, str]:
    """Czech weekday statutory holidays on which the GERMAN exchange is open -- the
    single-country closures where Prague is shut and Frankfurt trades.

    These are the only holiday rows CZ-K and CZ-L can learn anything from: a shared 25 December
    tells the desk nothing about Czechia. The German side is the statutory federal list plus
    24 December, on which Xetra does not trade even though it is not a public holiday.
    """
    german_md = {(1, 1), (5, 1), (10, 3), (12, 24), (12, 25), (12, 26)}
    easter = easter_sunday(year)
    german_moveable = {easter + timedelta(days=off) for off in (-2, 1, 39, 50)}
    out: dict[date, str] = {}
    for day, name in market_holidays(year).items():
        if (day.month, day.day) in german_md or day in german_moveable:
            continue
        out[day] = name
    return dict(sorted(out.items()))


# --------------------------------------------------------------------------- cells
def cells() -> tuple[dict[str, Any], ...]:
    """THE TESTABLE CELLS THIS PACK MINTS: domain x executable instrument x named condition.

    A cell is only honest if the pack's own data plane can evaluate its condition, so the
    conditions are the DOMAIN's declared conditions and the instruments are the DOMAIN's
    declared instruments -- never a cartesian product across the whole symbol list. That is why
    the count is a few over a hundred rather than the several hundred a blind cross product
    would produce.
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
                    "cell_id": f"CZ:{did}:{sym}:C{i}",
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
        "mission": MISSION, "floor_regime": FLOOR_REGIME, "interactions": INTERACTIONS,
        "cells": CELLS,
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
            "fixed_md": tuple(f"{m:02d}-{d:02d}" for m, d, _ in FIXED_STATE + FIXED_OTHER),
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
    `unmeasured` rather than left out, because an absence that is not named is an absence
    nobody schedules work against (L1.28a).
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
        "CNB decision calendar for 2026: not published in this pack (CENTRAL_BANK.dates_status)",
        "CZK positioning: no COT or exchange series exists; the MF CR holder structure is the "
        "only measure and it is monthly",
        "the CNB reserve COMPOSITION is annual, so the equity-tranche rebalancing flow is "
        "inferred and never observed",
        "forward power and carbon curves are LICENSED and registered machine_use_allowed=false",
    ]
    emitted = 0
    if ctx is not None:
        record = getattr(ctx, "record", None)
        note = getattr(ctx, "note", None)
        for row in rows:
            if callable(record):
                try:
                    record(**{"mechanism": f"cz_pack:{row.get('id') or row.get('with')}",
                              "payload": row})
                except TypeError:
                    record(row)
                emitted += 1
        if callable(note):
            for why in unmeasured:
                note("cz_pack:unmeasured", why)
    return {"code": CODE.lower(), "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "emitted": emitted, "rows": rows, "unmeasured": unmeasured,
            "cells_emitted": len(CELLS), "datasets": len(DATASETS), "actors": len(ACTORS),
            "domains": len(DOMAINS), "edges": len(TRANSMISSION_EDGES_SEED),
            "interactions": len(INTERACTIONS), "sources": len(SOURCE_CLASSES),
            "layers_covered": source_layer_coverage()["n_layers_covered"]}

