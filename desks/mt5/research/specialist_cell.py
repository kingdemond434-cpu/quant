#!/usr/bin/env python3
"""SPECIALIST RESEARCH CELLS: per-asset-class generators that mint the mechanisms a desk
specialist would name and a generic sweep never enumerates.

    python desks/mt5/research/specialist_cell.py --once --budget-s 900
    python desks/mt5/research/specialist_cell.py --once --dry-run     # measure, donate nothing

WHY. A generic sweep runs every family over every symbol on its defaults. What it cannot know is
that EURUSD's interesting minute is the WMR fix at 16:00 London, that crude reprices on the EIA
print at 10:30 New York on Wednesdays, that US500's month-end flow runs AGAINST its month-to-date
lead over bonds, or that corn's weather premium bleeds out after pollination. Each is a named
participant under an obligation at a known time -- the specialist's knowledge -- and each is
written below as (asset class, mechanism, family, the parameters that say it), with the prior
stated before any data was looked at.

THE CATALOGUE (`SPECIALISTS`):
  fx       wmr_fix_reversal, fix_forced_flow (WMR + Tokyo TTM), carry_risk_off,
           cb_meeting_drift (FOMC/ECB/BOE/BOJ, pre-meeting drift and post-decision fade)
  metals   gold_real_yield (gold against the bond proxy and the dollar), gold_silver_ratio,
           metals_fix (the London 4pm fix gold is benchmarked to)
  energy   eia_inventory (Wednesday EIA and Tuesday API windows)
  indices  overnight_gap, open_drive (the cash open of each index's own venue),
           month_end_rebalance (fixed-weight allocator flow), month_end_forced_flow
  softs    weather_window (per-commodity crop-cycle windows), wasde (USDA WASDE)
  tier-1   the 2026-11-11 ideas the build check of 2026-11-18 found unproduced (`TIER1_IDEAS`):
           intraday_momentum (U1, indices/gold/oil), overnight_day_tug (U2), weekend_crypto_lead
           (U4, JPY/AUD/gold/Nasdaq), earnings_gap_breadth (U5), pre_holiday_drift (N1). U2, U4,
           U5 and N1 need the families of `mt5desk/families_tier1.py`; until those are
           registered their cells are SET ASIDE BY NAME, and the report's `tier1_ideas` block
           says, per idea, which stage holds it back.

BUILDABLE BY THE SEALED GAUNTLET, OR NOT MINTED. Every cell is asked twice. First
`gauntlet_buildability.cell_verdict` (the family resolves, its data inputs are ones
`external_gauntlet.build_cell` supplies, its chart and params are complete); a cell that fails is
SET ASIDE BY NAME and counted. Then it is BUILT by the sealed `build_cell` itself -- not by a
reimplementation of it -- and its firing is measured on what that call returned, so a cell whose
peer or factor bars the gauntlet cannot load is counted as an input gap, never donated to come
back UNKNOWN. Where a mechanism needed a family that did not exist, it was registered in
`mt5desk/families_specialist.py` and loads its own inputs from the bar store given only what the
cell carries.

THE DOOR. Cells whose lower-bound trade days clear SEED_FLOOR are donated through
`proposer_common.donate` -- the two-lane filter, the point-in-time stamp, the preregistration and
the registry's `enqueue_candidate` -- into `data/intelligence/specialist_cell/`, which
`miner_candidate_compiler` compiles into the docket the gauntlet judges. The pass's trials are
priced by `libs.research.trial_ledger.census` over every cell MEASURED, not only those donated:
a specialist who looked at forty windows and donated three still searched forty.

ADDITIVE ONLY: no other miner is capped, reordered or slowed. A cell is measured at most once a
day (the state file carries the day), so a pass that runs out of budget resumes next hour.
UNMEASURED IS AN ANSWER (L1.28a): an input this host lacks is said, never read as zero.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
import time
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent          # desks/mt5
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(BASE / "scripts"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE = "specialist_cell"
OUT = BASE / "reports" / "SPECIALIST_CELLS.json"
STATE = BASE / "data" / "specialist_cell_state.json"
UNIVERSE = BASE / "data" / "universe" / "universe.json"
CANON = BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json"
UNMEASURED = "UNMEASURED"

#: The sealed gauntlet drops a daily series under 60 days; ten percent above it, as the class
#: books use, because a partial last day is trimmed and the cost model can refuse an entry.
FIRE_FLOOR = 60
SEED_FLOOR = 66
#: The principal's culture-provenance keys, exactly as named (2026-09-30).
CULTURE_KEYS = ("source_culture", "participant_structure", "failure_mode_hypothesis")


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _grid(spec: dict[str, list]) -> list[dict[str, Any]]:
    keys = sorted(spec)
    return [dict(zip(keys, combo, strict=True))
            for combo in itertools.product(*(spec[k] for k in keys))]


# ------------------------------------------------------------------------ asset classes ---
def asset_class(symbol: str) -> str | None:
    """The specialist desk a symbol belongs to, from MetaTrader's own registry class."""
    from research import universe_policy as up
    raw = str(up.asset_class_of(symbol) or "").strip().lower()
    if "forex" in raw or raw == "fx":
        return "fx"
    if raw in ("indices", "index"):
        return "indices" if symbol.upper() != "USDX" else None
    if raw == "energy":
        return "energy"
    if "soft" in raw:
        return "softs"
    if raw in ("commodity", "commodities", "metals", "metal"):
        return "metals"
    return None


def class_symbols() -> dict[str, list[str]]:
    from research import universe_policy as up
    out: dict[str, list[str]] = {}
    for sym in sorted(up._registry()):
        klass = asset_class(sym)
        if klass:
            out.setdefault(klass, []).append(sym)
    return out


# ---------------------------------------------------------------------------- catalogue ---
#: Broker hour of each index venue's cash open (broker = UTC+2 winter / UTC+3 summer; the list
#: carries both hours where the venue keeps no matching summer time, so neither season is lost).
OPEN_HOURS: dict[str, list[int]] = {
    "US500": [16, 17], "US30": [16, 17], "NAS100": [16, 17], "US2000": [16, 17],
    "CA60": [16, 17], "GER40": [10], "FRA40": [10], "EUSTX50": [10], "E35": [10],
    "NETH25": [10], "UK100": [10], "JPN225": [2, 3], "HK50": [3, 4], "CHINAH": [3, 4],
    "AUS200": [2, 3],
}
#: The bond proxy a balanced fund rebalances each index against.
BOND_OF: dict[str, str] = {"UK100": "UKGILT"}
#: Crop-cycle windows (MMDD, MMDD, side), each stated with its payer before any data was read.
WEATHER_WINDOWS: dict[str, list[tuple[int, int, int, str]]] = {
    "CORN": [(701, 831, -1, "US pollination weather premium bleeds out as the crop sets")],
    "SOYBEAN": [(715, 915, -1, "August pod-setting weather premium resolves into harvest")],
    "WHEAT": [(515, 715, -1, "northern-hemisphere winter-wheat harvest hedging pressure")],
    "COFARA": [(601, 831, 1, "Brazilian frost-season risk premium is bought by roasters")],
    "COFROB": [(601, 831, 1, "Brazilian/Vietnamese dry-season supply risk premium")],
    "SUGAR": [(401, 630, -1, "Brazil centre-south crush starts; mill hedging pressure")],
    "SUGARRAW": [(401, 630, -1, "Brazil centre-south crush starts; mill hedging pressure")],
    "USCOCOA": [(901, 1031, 1, "West African main-crop uncertainty before arrivals are known")],
    "UKCOCOA": [(901, 1031, 1, "West African main-crop uncertainty before arrivals are known")],
    "COTTON": [(701, 930, -1, "US crop weather premium resolves into harvest hedging")],
    "OJ": [(601, 1130, 1, "Florida hurricane-season risk premium is bought by processors")],
}
GOLD = ("XAUUSD", "XAUEUR", "XAUAUD")

# ------------------------------------------- the Tier-1 ideas of 2026-11-11 (build check) ---
#: U1 INTRADAY MOMENTUM (Gao, Han, Li & Zhou 2018; Elaut, Frommel & Lampaert 2018 on FX): the
#: first half-hour's return predicts the last half-hour's, same sign, on index, gold and oil
#: futures. On desk H1 bars it is `session_handoff` with both windows on the venue's OWN clock
#: (DST-exact, `mt5desk/local_clock.py`): the source is the bar containing the cash open (its
#: open-to-close move), the trade window is the bar that STARTS one hour before the close, so the
#: signal is decided at that bar's close and the position rides the closing hour. symbol ->
#: (zone, source "HH:MM" contains, trade "HH:MM" start). The H1 source bar includes the half-hour
#: before the open on US venues; that is the chart's resolution, named here rather than hidden.
INTRADAY_WINDOWS: dict[str, tuple[str, str, str]] = {
    **dict.fromkeys(("US500", "US30", "NAS100", "US2000"), ("America/New_York", "09:30",
                                                             "14:00")),
    **dict.fromkeys(("GER40", "EUSTX50", "FRA40", "NETH25", "E35"), ("Europe/Berlin", "09:00",
                                                                     "16:00")),
    "UK100": ("Europe/London", "08:00", "15:00"),
    "JPN225": ("Asia/Tokyo", "09:00", "14:00"),
    "AUS200": ("Australia/Sydney", "10:00", "15:00"),
    # COMEX gold opens 08:20 and settles 13:30 New York; NYMEX crude 09:00 and 14:30.
    **dict.fromkeys(("XAUUSD", "XAGUSD"), ("America/New_York", "08:20", "12:00")),
    **dict.fromkeys(("XTIUSD", "XBRUSD"), ("America/New_York", "09:00", "13:00")),
}
#: U2 OVERNIGHT-VS-DAY TUG OF WAR (Lou, Polk & Skouras 2019): each index's cash session in its
#: own zone, and the bars from the open bar to the close. symbol -> (zone, open, close, hold).
CASH_SESSIONS: dict[str, tuple[str, str, str, int]] = {
    **dict.fromkeys(("US500", "US30", "NAS100", "US2000"), ("America/New_York", "09:30",
                                                             "16:00", 6)),
    **dict.fromkeys(("GER40", "EUSTX50", "FRA40", "NETH25", "E35"), ("Europe/Berlin", "09:00",
                                                                     "17:30", 8)),
    "UK100": ("Europe/London", "08:00", "16:30", 8),
    "JPN225": ("Asia/Tokyo", "09:00", "15:30", 6),
    "AUS200": ("Australia/Sydney", "10:00", "16:00", 6),
    **dict.fromkeys(("HK50", "CHINAH"), ("Asia/Hong_Kong", "09:30", "16:00", 6)),
}
#: U4 WEEKEND CRYPTO AS A MONDAY-OPEN SIGNAL: Fusion's crypto CFDs trade through the weekend;
#: the instruments the idea names are shut. The driver is an MT5 instrument informing another
#: MT5 instrument (the mandate's one permitted use of crypto data), never a hunted universe.
WEEKEND_TARGETS = frozenset({"USDJPY", "AUDUSD", "AUDJPY", "XAUUSD", "NAS100"})
WEEKEND_DRIVERS = ("BTCUSD", "ETHUSD")
#: U5 EARNINGS-GAP BREADTH: the USD share-CFD class's opening gaps, read on the US indices.
GAP_BREADTH_TARGETS = frozenset({"US500", "NAS100", "US30", "US2000"})
#: N1 PRE-HOLIDAY DRIFT: the venue whose holiday calendar each index trades on. JPN225 is named
#: by the idea and absent here on purpose: the family does not generate the JPX calendar, so a
#: cell would fire nothing (`TIER1_IDEAS["N1"]["not_covered"]` says so in the report).
HOLIDAY_VENUE: dict[str, str] = {
    **dict.fromkeys(("US500", "US30", "NAS100", "US2000"), "NYSE"),
    **dict.fromkeys(("GER40", "EUSTX50"), "XETRA"), "UK100": "LSE",
}
#: The ideas, by the build check's id, and the (class, mechanism) units that carry them; the
#: report reads each unit's counts back so "what stops it producing" is a measurement.
TIER1_IDEAS: dict[str, dict[str, Any]] = {
    "U1": {"idea": "intraday momentum: first half-hour predicts last half-hour",
           "units": [("indices", "intraday_momentum"), ("metals", "intraday_momentum"),
                     ("energy", "intraday_momentum")], "family": "session_handoff"},
    "U2": {"idea": "overnight-vs-day tug of war on index CFDs",
           "units": [("indices", "overnight_day_tug")], "family": "overnight_intraday_tug"},
    "U4": {"idea": "weekend crypto as the Monday-open signal for JPY, AUD, gold, Nasdaq",
           "units": [("fx", "weekend_crypto_lead"), ("metals", "weekend_crypto_lead"),
                     ("indices", "weekend_crypto_lead")], "family": "weekend_driver_gap"},
    "U5": {"idea": "share-CFD earnings-gap breadth as a next-day index signal",
           "units": [("indices", "earnings_gap_breadth")], "family": "equity_gap_breadth"},
    "N1": {"idea": "Western pre-holiday drift on index CFDs",
           "units": [("indices", "pre_holiday_drift")], "family": "pre_holiday_drift",
           "not_covered": {"JPN225": "the JPX holiday calendar is not generated by the family"}},
}


def _intraday(sym: str) -> list[tuple[str, str, list[dict[str, Any]]]]:
    w = INTRADAY_WINDOWS.get(sym.upper())
    if not w:
        return []
    tz, src, trd = w
    return [("intraday_momentum", "session_handoff",
             _grid({"source_tz": [tz], "source_at": [src], "source_align": ["contains"],
                    "trade_tz": [tz], "trade_at": [trd], "trade_align": ["start"],
                    "source_bars": [1], "hold_bars": [1], "direction": [1],
                    "min_info_atr": [0.0, 0.3]}))]


def _weekend(sym: str) -> list[tuple[str, str, list[dict[str, Any]]]]:
    if sym.upper() not in WEEKEND_TARGETS:
        return []
    return [("weekend_crypto_lead", "weekend_driver_gap",
             _grid({"driver_symbol": list(WEEKEND_DRIVERS), "entry_z": [0.5, 1.0],
                    "direction": [1, -1], "hold_bars": [6, 24]}))]


def _fx(sym: str) -> list[tuple[str, str, list[dict[str, Any]]]]:
    return _weekend(sym) + [
        ("wmr_fix_reversal", "fx_fixing_reversal",
         _grid({"fix_hour": [18, 19], "pre_window_bars": [2, 3],
                "min_displacement_atr": [0.6, 1.0], "hold_bars": [3, 6]})),
        ("fix_forced_flow", "forced_flow",
         _grid({"event_kind": ["fixing"], "clock": ["utc"], "symbol": [sym],
                "mode": ["pre_flow", "post_flow_fade"]})),
        ("carry_risk_off", "carry_risk_off",
         _grid({"symbol": [sym], "mode": ["harvest", "unwind"],
                "risk_symbol": ["US500", "JPN225"], "z_thr": [1.0, 1.5], "hold_d": [1, 5]})),
        ("cb_meeting_drift", "forced_flow",
         [{"event_kind": "central_bank", "clock": "utc", "symbol": sym, "mode": "pre_flow",
           "window_before_min": w} for w in (240, 1440)]
         + [{"event_kind": "central_bank", "clock": "utc", "symbol": sym,
             "mode": "post_flow_fade", "window_after_min": w} for w in (90, 240)]),
    ]


def _metals(sym: str) -> list[tuple[str, str, list[dict[str, Any]]]]:
    out: list[tuple[str, str, list[dict[str, Any]]]] = []
    if sym in GOLD:
        out.append(("gold_real_yield", "cross_asset_residual",
                    _grid({"factor_symbols": [["UST10Y", "USDX"]],
                           "side_mode": ["revert", "follow"], "lookback": [240, 480],
                           "entry_z": [1.5, 2.0]})))
    if sym in ("XAUUSD", "XAGUSD"):
        out.append(("gold_silver_ratio", "relative_value",
                    _grid({"peer_symbol": ["XAGUSD" if sym == "XAUUSD" else "XAUUSD"],
                           "lookback": [120, 480], "entry_z": [2.0, 2.5]})))
    out.append(("metals_fix", "forced_flow",
                _grid({"event_kind": ["fixing"], "clock": ["utc"], "symbol": [sym],
                       "mode": ["pre_flow", "post_flow_fade"]})))
    return out + _intraday(sym) + _weekend(sym)


def _energy(sym: str) -> list[tuple[str, str, list[dict[str, Any]]]]:
    return [("eia_inventory", "forced_flow",
             _grid({"event_kind": ["inventory"], "clock": ["utc"], "symbol": [sym],
                    "mode": ["pre_flow", "post_flow_fade"], "window_after_min": [45, 120]}))
            ] + _intraday(sym)


def _indices(sym: str) -> list[tuple[str, str, list[dict[str, Any]]]]:
    out: list[tuple[str, str, list[dict[str, Any]]]] = [
        ("overnight_gap", "overnight_gap_decay",
         _grid({"gap_atr": [0.5, 0.75, 1.0], "ttl_bars": [4, 8]})),
        ("month_end_rebalance", "month_end_rebalance",
         _grid({"bond_symbol": [BOND_OF.get(sym, "UST10Y")], "days_before": [2, 3],
                "min_gap_sd": [0.5, 1.0]})),
        ("month_end_forced_flow", "forced_flow",
         _grid({"event_kind": ["month_end"], "clock": ["utc"], "symbol": [sym],
                "mode": ["pre_flow", "post_flow_fade"]})),
    ]
    hours = OPEN_HOURS.get(sym.upper())
    if hours:
        out.append(("open_drive", "opening_range",
                    _grid({"open_hour": hours, "range_bars": [1], "window_bars": [6],
                           "rr": [1.5, 2.0]})))
    s = sym.upper()
    out += _intraday(sym) + _weekend(sym)
    if s in CASH_SESSIONS:
        tz, op, cl, hold = CASH_SESSIONS[s]
        out.append(("overnight_day_tug", "overnight_intraday_tug",
                    _grid({"venue_tz": [tz], "open_at": [op], "close_at": [cl],
                           "min_leg_atr": [0.2, 0.5], "direction": [-1, 1],
                           "hold_bars": [hold]})))
    if s in GAP_BREADTH_TARGETS:
        out.append(("earnings_gap_breadth", "equity_gap_breadth",
                    _grid({"peer_currency": ["USD"], "gap_min": [0.03, 0.05],
                           "entry_breadth": [0.05, 0.1], "direction": [1, -1],
                           "hold_bars": [22]})))
    if s in HOLIDAY_VENUE:
        out.append(("pre_holiday_drift", "pre_holiday_drift",
                    [{"venue": HOLIDAY_VENUE[s], "days_before": k, "side": 1,
                      "hold_bars": 23 * k} for k in (1, 2)]))
    return out


def _softs(sym: str) -> list[tuple[str, str, list[dict[str, Any]]]]:
    out: list[tuple[str, str, list[dict[str, Any]]]] = []
    wins = WEATHER_WINDOWS.get(sym.upper())
    if wins:
        out.append(("weather_window", "seasonal_window",
                    [{"start_md": a, "end_md": b, "side_bias": s, "hold_d": h}
                     for a, b, s, _why in wins for h in (1, 3)]))
    out.append(("wasde", "forced_flow",
                _grid({"event_kind": ["usda"], "clock": ["utc"], "symbol": [sym],
                       "mode": ["pre_flow", "post_flow_fade"]})))
    return out


#: class -> (per-symbol cell generator, the specialist's priors per mechanism). The priors are
#: carried onto every donated row as its mechanism text.
SPECIALISTS: dict[str, tuple[Callable[[str], list[tuple[str, str, list[dict[str, Any]]]]],
                             dict[str, str]]] = {
    "fx": (_fx, {
        "weekend_crypto_lead": "a weekend risk shock priced only by Fusion crypto CFDs reaches "
                               "JPY and AUD at the Monday open, which may under-react",
        "wmr_fix_reversal": "benchmark trackers must transact AT the WMR 4pm London fix; the "
                            "pre-fix displacement is impact and reverses once they are done",
        "fix_forced_flow": "WMR and Tokyo TTM fixings: the forced participant is the benchmarked "
                           "fund or the corporate settling at the published rate",
        "carry_risk_off": "levered carry is harvested in calm and margin-called in risk-off "
                          "(Brunnermeier, Nagel & Pedersen 2008)",
        "cb_meeting_drift": "rates desks re-hedge the front end into and out of a scheduled "
                            "central-bank decision (Lucca & Moench 2015 pre-announcement drift)",
    }),
    "metals": (_metals, {
        "intraday_momentum": "late-day hedgers and informed traders who waited for the open's "
                             "information trade the close in its direction (Gao et al. 2018)",
        "weekend_crypto_lead": "a risk shock priced by Fusion crypto CFDs over the weekend reaches "
                               "gold only at the Monday open, which may under-react",
        "gold_real_yield": "gold is priced off the real rate and the dollar; a gap between gold "
                           "and the bond proxy plus USDX closes as the arbitrage is worked",
        "gold_silver_ratio": "the gold/silver ratio mean-reverts as relative-value holders "
                             "trade its extremes",
        "metals_fix": "bullion is benchmarked to the London 4pm fix; the benchmarked holder must "
                      "transact at it",
    }),
    "energy": (_energy, {
        "intraday_momentum": "late-day hedgers and informed traders who waited for the open's "
                             "information trade the close in its direction (Gao et al. 2018)",
        "eia_inventory": "refiners and index hedgers must resize on the statutory Wednesday EIA "
                         "print (and position into it on the Tuesday API number)",
    }),
    "indices": (_indices, {
        "intraday_momentum": "short-gamma dealers and late informed traders push the close in "
                             "the direction the open set (Gao, Han, Li & Zhou 2018)",
        "overnight_day_tug": "overnight and intraday clienteles disagree; when the night leg "
                             "contradicts yesterday's day leg the day session reverses it (Lou, "
                             "Polk & Skouras 2019)",
        "weekend_crypto_lead": "a weekend risk shock priced only by Fusion crypto CFDs reaches "
                               "the index at the Monday open, which may under-react",
        "earnings_gap_breadth": "a broad share of single names gapping on earnings is news the "
                                "index has only partly absorbed; the next session continues it",
        "pre_holiday_drift": "short sellers cover and buyers front-run the holiday close; index "
                             "returns before exchange holidays are abnormally positive (Ariel "
                             "1990; Lakonishok & Smidt 1988)",
        "overnight_gap": "the cash open prices the overnight gap and the liquidity provider who "
                         "absorbed it is paid as it decays",
        "open_drive": "the cash open concentrates the venue's own order flow; the first range "
                      "breaks in the direction of the imbalance",
        "month_end_rebalance": "fixed-weight balanced funds sell the asset that out-ran the other "
                               "month-to-date in the month's last days",
        "month_end_forced_flow": "month-end benchmark and index rebalancing flow on a dated "
                                 "calendar",
    }),
    "softs": (_softs, {
        "weather_window": "a crop-cycle weather premium is bought by hedgers at any price and "
                          "bleeds out as the risk resolves",
        "wasde": "merchandisers must re-hedge on the USDA WASDE balance sheet at a published "
                 "minute",
    }),
}


# ------------------------------------------------------------------- culture provenance ---
#: The principal's order of 2026-09-30: every cell carries `source_culture`,
#: `participant_structure` and `failure_mode_hypothesis`. A specialist mechanism is anchored to
#: the venue, fix or crop whose participants create it, so the tag is that jurisdiction's, stated
#: here once; a mechanism with no single home is GLOBAL, and nothing is guessed.
WESTERN_STANDARD = ("this is the standard Western version of the mechanism; no culture-specific "
                    "failure timing is claimed for it")
VENUE_CULTURE: dict[str, str] = {
    "US500": "US", "US30": "US", "NAS100": "US", "US2000": "US", "CA60": "CA", "GER40": "DE",
    "FRA40": "FR", "EUSTX50": "EU", "E35": "ES", "NETH25": "NL", "UK100": "GB",
    "JPN225": "JP", "HK50": "HK", "CHINAH": "CN", "AUS200": "AU",
}
CROP_CULTURE: dict[str, str] = {
    "CORN": "US", "SOYBEAN": "US", "WHEAT": "US", "COTTON": "US", "OJ": "US",
    "COFARA": "BR", "COFROB": "VN", "SUGAR": "BR", "SUGARRAW": "BR",
    "USCOCOA": "CI", "UKCOCOA": "CI",
}
_WESTERN = frozenset({"US", "CA", "GB", "DE", "FR", "EU", "ES", "NL", "AU"})
_MECH_CULTURE: dict[str, tuple[str, str]] = {
    "wmr_fix_reversal": ("GB", "institutional"),
    "fix_forced_flow": ("GLOBAL", "settlement_constrained"),
    "carry_risk_off": ("GLOBAL", "institutional"),
    "cb_meeting_drift": ("GLOBAL", "policy_driven"),
    "gold_real_yield": ("US", "institutional"),
    "gold_silver_ratio": ("GLOBAL", "mixed"),
    "metals_fix": ("GB", "institutional"),
    "eia_inventory": ("US", "physical_flow"),
    "month_end_forced_flow": ("GLOBAL", "institutional"),
    "wasde": ("US", "policy_driven"),
    "intraday_momentum": ("US", "institutional"),
    "weekend_crypto_lead": ("GLOBAL", "retail_heavy"),
}


def culture(mechanism: str, symbol: str) -> dict[str, str]:
    """`source_culture`, `participant_structure`, `failure_mode_hypothesis` for one cell."""
    sym = symbol.upper()
    if mechanism in ("overnight_gap", "open_drive", "month_end_rebalance") or (
            mechanism in ("intraday_momentum", "overnight_day_tug", "earnings_gap_breadth",
                          "pre_holiday_drift")
            and sym in VENUE_CULTURE):
        tag = VENUE_CULTURE.get(sym, "UNMEASURED")
        part = "mixed" if mechanism == "overnight_gap" else "institutional"
        why = (WESTERN_STANDARD if tag in _WESTERN else
               f"the flow is the {tag} cash session's own participants on its own holiday, "
               "settlement and policy calendar, so it should fail when that calendar or that "
               "market's domestic flow shifts rather than with the US session"
               if tag != "UNMEASURED" else "UNMEASURED: the venue of this index is not declared")
        return {"source_culture": tag, "participant_structure": part,
                "failure_mode_hypothesis": why}
    if mechanism == "weather_window":
        tag = CROP_CULTURE.get(sym, "UNMEASURED")
        why = (WESTERN_STANDARD if tag in _WESTERN else
               f"the premium is set by the {tag} crop's own weather and its local producers' "
               "hedging and export policy, so it should fail when that country's harvest or "
               "policy calendar moves, independently of Western demand"
               if tag != "UNMEASURED" else "UNMEASURED: the producing country is not declared")
        return {"source_culture": tag, "participant_structure": "physical_flow",
                "failure_mode_hypothesis": why}
    tag, part = _MECH_CULTURE.get(mechanism, ("UNMEASURED", "UNMEASURED"))
    if mechanism == "fix_forced_flow":
        why = ("the calendar joins the London WMR fix and the Tokyo TTM; the TTM leg is Japanese "
               "corporates settling invoices at their bank's 09:55 rate, which concentrates on "
               "gotobi days and month-end and so fails on the Japanese settlement calendar, not "
               "on London benchmark reform")
    elif tag == "GLOBAL":
        why = ("region-agnostic: the payer is a global class of participant, so no single "
               "culture's failure timing is claimed")
    elif tag == "UNMEASURED":
        why = "UNMEASURED"
    else:
        why = WESTERN_STANDARD
    return {"source_culture": tag, "participant_structure": part,
            "failure_mode_hypothesis": why}


def plan(symbols_by_class: dict[str, list[str]] | None = None) -> list[dict[str, Any]]:
    """Every (class, mechanism, symbol, family, params) the catalogue names, lane-filtered."""
    from research import universe_policy as up
    by_class = symbols_by_class if symbols_by_class is not None else class_symbols()
    out: list[dict[str, Any]] = []
    for klass, (gen, priors) in SPECIALISTS.items():
        for sym in by_class.get(klass, []):
            for mech, fam, grid in gen(sym):
                if not up.may_hypothesise(sym, fam):
                    continue
                for params in grid:
                    out.append({"klass": klass, "mechanism": mech, "symbol": sym,
                                "family": fam, "params": params,
                                "prior": priors.get(mech, ""), **culture(mech, sym)})
    return out


def identity(symbol: str, family: str, params: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps({"s": symbol, "f": family, "p": params}, sort_keys=True,
                                     default=str).encode()).hexdigest()[:20]


# -------------------------------------------------------------------------- measurement ---
def _meta() -> dict[str, Any]:
    doc = _read(UNIVERSE)
    if isinstance(doc, dict) and isinstance(doc.get("symbols"), dict):
        return doc["symbols"]
    return doc if isinstance(doc, dict) else {}


def measure(sym: str, family: str, params: dict[str, Any], meta: dict[str, Any]
            ) -> dict[str, Any]:
    """Build the cell through the SEALED `build_cell` and count how it fires on what it built."""
    import external_gauntlet as eg
    from research.cross_sectional_breadth import firing
    try:
        cell = eg.build_cell(sym, family, dict(params), meta)
    except Exception as exc:
        return {"built": False, "why": f"build_cell raised {type(exc).__name__}: {exc}"[:240]}
    if cell is None:
        return {"built": False, "why": str(getattr(eg, "LAST_BUILD_FAILURE", None)
                                           or "build_cell returned None")[:240]}
    got = firing(list(cell.get("sigs") or []), cell["df"])
    return {"built": True, **got}


def breadth_unit(klass: str, mechanism: str) -> str:
    """ONE MECHANISM IS ONE BREADTH UNIT, however many (symbol, parameter) points it is minted on.

    Measured 2026-09-30: 352 of the 370 cells that cleared the floor were `wmr_fix_reversal` --
    one participant (the benchmark tracker at the WMR fix) on 22 FX symbols x 16 parameter
    points. Counted as cells, the organ reported 370 units of breadth; counted as independent
    bets it had two or three. Every cell is still measured, charged to the trial census and
    donated (no mining is reduced); breadth is counted by this key."""
    return f"{klass}/{mechanism}"


def family_grids(cells: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per breadth unit: the family, and the DISTINCT symbols and parameter points it spans --
    one family grid per mechanism, never one breadth unit per cell."""
    out: dict[str, dict[str, Any]] = {}
    pts: dict[str, set[str]] = {}
    syms: dict[str, set[str]] = {}
    fams: dict[str, set[str]] = {}
    for c in cells:
        u = breadth_unit(str(c["klass"]), str(c["mechanism"]))
        pts.setdefault(u, set()).add(json.dumps(c["params"], sort_keys=True, default=str))
        syms.setdefault(u, set()).add(str(c["symbol"]))
        fams.setdefault(u, set()).add(str(c["family"]))
        out.setdefault(u, {"cells": 0})["cells"] += 1
    for u, row in out.items():
        row.update({"families": sorted(fams[u]), "symbols": len(syms[u]),
                    "param_points": len(pts[u])})
    return dict(sorted(out.items(), key=lambda kv: -int(kv[1]["cells"])))


def breadth(cells: list[dict[str, Any]]) -> dict[str, Any]:
    """k-style breadth of a set of cells: the number of distinct MECHANISMS, beside the raw cell
    count and the largest mechanism's share, so a grid cannot pass for independent bets."""
    grids = family_grids(cells)
    top = next(iter(grids.items()), (None, {"cells": 0}))
    return {"cells": len(cells), "breadth_k": len(grids),
            "largest_unit": top[0], "largest_unit_share": (round(top[1]["cells"] / len(cells), 4)
                                                           if cells else 0.0),
            "family_grids": grids,
            "rule": ("breadth counts a mechanism ONCE (asset-class desk / mechanism); its "
                     "symbols and parameter points are one family grid. Every cell is still "
                     "charged to the trial census and donated")}


def charge(cells: list[dict[str, Any]]) -> dict[str, Any]:
    """This pass's multiplicity, priced by the desk's effective-trial ledger over every cell
    MEASURED -- the specialist's whole search, not only what cleared the floor."""
    if not cells:
        return {"n_raw": 0, "n_effective": 0.0, "basis": "no cell measured this pass"}
    try:
        from libs.research import trial_ledger as tl
        c = tl.census([tl.Trial(identity(r["symbol"], r["family"], r["params"]), r["family"],
                                {"mechanism": r["mechanism"], "asset_class": r["klass"],
                                 "symbol": r["symbol"]},
                                {k: v for k, v in r["params"].items()
                                 if isinstance(v, (int, float, str, bool))})
                       for r in cells])
    except Exception as exc:
        return {"n_raw": len(cells), "n_effective": None,
                "basis": f"{UNMEASURED}: trial_ledger failed ({type(exc).__name__}: {exc})"}
    return {"n_raw": int(c.n_raw), "n_effective": round(float(c.n_effective), 2),
            "inflation": round(float(c.inflation), 3), "n_families": len(c.families),
            "basis": ("libs.research.trial_ledger.census over every cell measured this pass; "
                      "donated rows are charged again by the gauntlet's own census when judged")}


def _load_state() -> dict[str, Any]:
    doc = _read(STATE)
    return doc if isinstance(doc, dict) and isinstance(doc.get("cells"), dict) else {"cells": {}}


def _save_state(state: dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True), "utf-8")
    tmp.replace(STATE)


def seed(*, budget_s: float = 900.0, dry_run: bool = False,
         symbols_by_class: dict[str, list[str]] | None = None) -> dict[str, Any]:
    """Verdict, build, measure and donate. Never raises out of a single cell."""
    from research.gauntlet_buildability import BUILDABLE, cell_verdict
    started = time.monotonic()
    today = datetime.now(tz=UTC).date().isoformat()
    try:
        cells = plan(symbols_by_class)
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"catalogue unresolvable: {type(exc).__name__}"}
    meta = _meta()
    state = _load_state()
    cs: dict[str, Any] = state["cells"]
    rows: dict[tuple[str, str], Counter] = {}
    set_aside: Counter = Counter()
    input_gaps: Counter = Counter()
    no_bars: set[str] = set()
    measured_now: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    clearing: list[dict[str, Any]] = []
    stopped = "catalogue exhausted"
    for c in cells:
        key = (c["klass"], c["mechanism"])
        row = rows.setdefault(key, Counter())
        row["grid"] += 1
        verdict, why = cell_verdict(c["family"], c["params"])
        if verdict != BUILDABLE:
            row["set_aside_unbuildable"] += 1
            set_aside[f"{c['family']}: {verdict}: {why[:120]}"] += 1
            continue
        row["buildable"] += 1
        ident = identity(c["symbol"], c["family"], c["params"])
        prior = cs.get(ident) or {}
        if prior.get("day") != today:
            if time.monotonic() - started > budget_s:
                stopped = f"time budget {budget_s:g}s reached; resumes next pass"
                row["not_reached_this_pass"] += 1
                continue
            got = measure(c["symbol"], c["family"], c["params"], meta)
            prior = {**prior, **got, "day": today, **{k: c[k] for k in
                                                      ("klass", "mechanism", "symbol",
                                                       "family", "params")}}
            cs[ident] = prior
            measured_now.append(c)
            row["measured_this_pass"] += 1
        if not prior.get("built"):
            row["input_gap"] += 1
            why = str(prior.get("why"))
            if why.startswith("no ") and " bars for " in why:
                no_bars.add(c["symbol"])
                why = why.split(" bars for ")[0] + " bars for <symbol>"
            input_gaps[f"{c['family']}: {why[:120]}"] += 1
            continue
        if not int(prior.get("signal_days") or 0):
            # BUILT AND SILENT is its own finding: an input the family reads (the swap terms, a
            # proxy's bars, the measured bar clock a UTC calendar needs) is absent on this host
            row["built_but_zero_signals"] += 1
        ok = int(prior.get("trade_days_lb") or 0) >= SEED_FLOOR
        row["clears_floor" if ok else "held_back_under_floor"] += 1
        if ok:
            clearing.append(c)
        if ok and not prior.get("donated_at"):
            cands.append({**c, "ident": ident,
                          "firing": {k: prior.get(k) for k in ("signal_days", "trade_days_lb")}})

    donation: dict[str, Any] = {"status": "DRY_RUN" if dry_run else "NOTHING_NEW"}
    if cands and not dry_run:
        from research import proposer_common as pc
        out_rows = [pc.candidate(
            SOURCE, c["symbol"], c["family"], c["params"],
            f"{c['mechanism']} ({c['klass']} specialist): {c['prior']}",
            f"{c['symbol']} {c['mechanism']} via {c['family']}",
            {"firing": c["firing"], "seed_floor": SEED_FLOOR, "gauntlet_floor": FIRE_FLOOR,
             "asset_class_desk": c["klass"], "specialist_mechanism": c["mechanism"],
             "built_by": "external_gauntlet.build_cell (sealed), measured on its own output"})
            for c in cands]
        grids = family_grids(cands)
        for row, c in zip(out_rows, cands, strict=True):
            row.update({k: c[k] for k in CULTURE_KEYS})
            # One family grid per mechanism: every row of it names the same unit, so a reader
            # of the donation counts the mechanism once however many cells it carries.
            unit = breadth_unit(c["klass"], c["mechanism"])
            row["breadth_unit"] = unit
            row["family_grid"] = {"id": unit, **grids[unit]}
        path = pc.donate(SOURCE, out_rows, len(measured_now) or len(out_rows))
        counts = pc.donation_counts()
        donation = {"status": "DONATED" if path else "REFUSED_AT_DOOR",
                    "path": str(path) if path else None,
                    "donated": counts.get("donated"),
                    "refused_wrong_lane": counts.get("refused_wrong_lane"),
                    "refused_unstamped": counts.get("refused_unstamped"),
                    "registry_error": counts.get("registry_error")}
        if path:
            at = _now()
            for c in cands:
                cs[c["ident"]]["donated_at"] = at
                rows[(c["klass"], c["mechanism"])]["seeded_this_pass"] += 1
    if not dry_run:
        _save_state(state)
    seeded = Counter((str(v.get("klass")), str(v.get("mechanism")))
                     for v in cs.values() if v.get("donated_at"))
    by_mech = []
    for (klass, mech), cnt in sorted(rows.items()):
        cnt["seeded_total"] = seeded.get((klass, mech), 0)
        by_mech.append({"asset_class": klass, "mechanism": mech, **dict(cnt)})
    return {
        "status": "OK", "dry_run": bool(dry_run), "stopped_because": stopped,
        "elapsed_s": round(time.monotonic() - started, 2),
        "seed_floor_trade_days": SEED_FLOOR, "gauntlet_floor_days": FIRE_FLOOR,
        "cells_in_catalogue": len(cells), "measured_this_pass": len(measured_now),
        "candidates_this_pass": len(cands), "donation": donation,
        "trial_charge_this_pass": charge(measured_now),
        "breadth_clearing_floor": breadth(clearing),
        "breadth_donated_this_pass": breadth(cands),
        "by_mechanism": by_mech,
        "set_aside_unbuildable": dict(set_aside.most_common(40)),
        "input_gaps": dict(input_gaps.most_common(40)),
        "symbols_without_bars": sorted(no_bars),
    }


# ---------------------------------------------------------------------------- the report ---
def _certificates() -> dict[str, Any]:
    """Certificates in the canon whose exact (symbol, family, params) this organ donated."""
    state = _load_state()["cells"]
    donated = {identity(v["symbol"], v["family"], v["params"]): v for v in state.values()
               if v.get("donated_at") and v.get("symbol")}
    if not donated:
        return {"status": UNMEASURED, "why": "no specialist cell donated yet"}
    doc = _read(CANON)
    if not isinstance(doc, dict) or not isinstance(doc.get("survivors"), dict):
        return {"status": UNMEASURED, "why": f"{CANON.name} absent or unreadable"}
    hit: Counter = Counter()
    for cert in doc["survivors"].values():
        spec = cert.get("shadow_spec") if isinstance(cert, dict) else None
        if not isinstance(spec, dict):
            continue
        v = donated.get(identity(str(spec.get("symbol") or ""), str(spec.get("family") or ""),
                                 spec.get("params") or {}))
        if v:
            hit[f"{v['klass']}/{v['mechanism']}"] += 1
    return {"status": "MEASURED", "donated_cells": len(donated),
            "certified_by_mechanism": dict(hit), "certified_total": int(sum(hit.values()))}


def _culture_census() -> dict[str, Any]:
    try:
        cells = plan()
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    return {"status": "MEASURED",
            "source_culture": dict(Counter(c["source_culture"] for c in cells)),
            "participant_structure": dict(Counter(c["participant_structure"] for c in cells))}


def tier1_ideas(seeded: dict[str, Any]) -> dict[str, Any]:
    """Per Tier-1 idea: its family's verdict and its units' counts, and the FIRST stage that
    holds it back -- the family not yet buildable, an input gap, cells built but silent, cells
    under the trade-day floor, or none (it seeds)."""
    try:
        from research.gauntlet_buildability import family_verdict
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    rows = {(r.get("asset_class"), r.get("mechanism")): r
            for r in seeded.get("by_mechanism") or []}
    out: dict[str, Any] = {}
    for key, spec in TIER1_IDEAS.items():
        verdict, why = family_verdict(spec["family"])
        units = {f"{k}/{m}": {c: v for c, v in (rows.get((k, m)) or {}).items()
                              if c not in ("asset_class", "mechanism")}
                 for k, m in spec["units"]}
        tot: Counter = Counter()
        for u in units.values():
            tot.update({k: int(v) for k, v in u.items() if isinstance(v, int)})
        if not tot.get("grid"):
            stage = f"{UNMEASURED}: no cell of this idea was planned on this host"
        elif tot.get("set_aside_unbuildable", 0) >= tot["grid"]:
            stage = f"family {spec['family']} not buildable: {verdict}"
        elif tot.get("seeded_total"):
            stage = "SEEDING"
        elif tot.get("clears_floor"):
            stage = "clears the floor; donation pending"
        elif tot.get("held_back_under_floor"):
            stage = f"built but under the {SEED_FLOOR}-trade-day floor"
        elif tot.get("built_but_zero_signals"):
            stage = "built and silent: an input the family reads is absent here"
        elif tot.get("input_gap"):
            stage = "input gap: the sealed build_cell could not build it"
        else:
            stage = "not reached this pass (time budget)"
        out[key] = {"idea": spec["idea"], "family": spec["family"], "family_verdict": verdict,
                    "family_why": why, "units": units, "totals": dict(tot),
                    "holding_it_back": stage, **({"not_covered": spec["not_covered"]}
                                                 if spec.get("not_covered") else {})}
    return out


def report(seeded: dict[str, Any]) -> dict[str, Any]:
    new_families = {}
    try:
        from mt5desk.families_specialist import INPUTS
        from research.gauntlet_buildability import family_verdict, foreign_series, \
            information_class
        for fam in INPUTS:
            v, why = family_verdict(fam)
            new_families[fam] = {"verdict": v, "why": why, "inputs": INPUTS[fam][0],
                                 "information": information_class(fam),
                                 "foreign_series": foreign_series(fam)}
    except Exception as exc:
        new_families = {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    return {
        "at": _now(), "organ": "desks/mt5/research/specialist_cell.py",
        "rule": ("each cell is a specialist's named mechanism on one symbol; it is minted only "
                 "when gauntlet_buildability says the sealed gauntlet can build it AND the sealed "
                 f"build_cell does build it with >= {SEED_FLOOR} lower-bound trade days; every "
                 "measured cell is charged to the trial census. Additive: no other miner is "
                 "capped, reordered or slowed"),
        "catalogue": {k: sorted(v[1]) for k, v in SPECIALISTS.items()},
        "culture_of_catalogue": _culture_census(),
        "new_families": new_families,
        "tier1_ideas": tier1_ideas(seeded),
        "seeding": seeded,
        "certificates": _certificates(),
        "consumer": ("data/intelligence/specialist_cell/ -> research/miner_candidate_compiler.py "
                     "-> the docket -> scripts/external_gauntlet.py build_cell (sealed)"),
    }


def run(*, budget_s: float = 900.0, dry_run: bool = False, out: Path | None = None,
        symbols_by_class: dict[str, list[str]] | None = None) -> dict[str, Any]:
    doc = report(seed(budget_s=budget_s, dry_run=dry_run, symbols_by_class=symbols_by_class))
    target = out or OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(target)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true", help="one pass (the scheduled form)")
    ap.add_argument("--budget-s", type=float, default=900.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    doc = run(budget_s=args.budget_s, dry_run=args.dry_run, out=args.out)
    s = doc["seeding"]
    print(f"specialist_cell: {s.get('status')} catalogue={s.get('cells_in_catalogue')} "
          f"measured={s.get('measured_this_pass')} candidates={s.get('candidates_this_pass')} "
          f"donation={(s.get('donation') or {}).get('status')} "
          f"stopped={s.get('stopped_because')!r} -> {args.out or OUT}")
    for r in s.get("by_mechanism") or []:
        print(f"  {r['asset_class']:8} {r['mechanism']:24} grid={r.get('grid', 0):5} "
              f"clears={r.get('clears_floor', 0):4} held={r.get('held_back_under_floor', 0):4} "
              f"gap={r.get('input_gap', 0):4} seeded={r.get('seeded_total', 0):4}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
