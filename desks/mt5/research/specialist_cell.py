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


def _fx(sym: str) -> list[tuple[str, str, list[dict[str, Any]]]]:
    return [
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
    return out


def _energy(sym: str) -> list[tuple[str, str, list[dict[str, Any]]]]:
    return [("eia_inventory", "forced_flow",
             _grid({"event_kind": ["inventory"], "clock": ["utc"], "symbol": [sym],
                    "mode": ["pre_flow", "post_flow_fade"], "window_after_min": [45, 120]}))]


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
        "gold_real_yield": "gold is priced off the real rate and the dollar; a gap between gold "
                           "and the bond proxy plus USDX closes as the arbitrage is worked",
        "gold_silver_ratio": "the gold/silver ratio mean-reverts as relative-value holders "
                             "trade its extremes",
        "metals_fix": "bullion is benchmarked to the London 4pm fix; the benchmarked holder must "
                      "transact at it",
    }),
    "energy": (_energy, {
        "eia_inventory": "refiners and index hedgers must resize on the statutory Wednesday EIA "
                         "print (and position into it on the Tuesday API number)",
    }),
    "indices": (_indices, {
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
}


def culture(mechanism: str, symbol: str) -> dict[str, str]:
    """`source_culture`, `participant_structure`, `failure_mode_hypothesis` for one cell."""
    sym = symbol.upper()
    if mechanism in ("overnight_gap", "open_drive", "month_end_rebalance"):
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
        for row, c in zip(out_rows, cands, strict=True):
            row.update({k: c[k] for k in CULTURE_KEYS})
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


def report(seeded: dict[str, Any]) -> dict[str, Any]:
    new_families = {}
    try:
        from mt5desk.families_specialist import INPUTS
        from research.gauntlet_buildability import family_verdict
        for fam in INPUTS:
            v, why = family_verdict(fam)
            new_families[fam] = {"verdict": v, "why": why, "inputs": INPUTS[fam][0]}
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
