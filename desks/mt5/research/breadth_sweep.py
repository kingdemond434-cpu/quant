"""CLOSE THE NAMED BREADTH GAPS BY GENERATING THEIR CELLS.

The breadth board lists seven families the book does not hold and marks each REACHABLE with the
input it needs. REACHABLE means the constructor already exists on this tree and the family has
simply never been swept -- so the gap is not research, it is a docket that was never written.

WHY THIS IS THE HIGHEST-VALUE SWEEP ON THE DESK. Measured 2026-09-12: 15 funded sleeves behave as
~7.9 INDEPENDENT bets (n_eff covariance), the largest mechanism is 60% of the book, and the growth
curve stops paying above 22.5% heat BECAUSE of that concentration. The ceiling is set by n_eff,
not by sleeve count -- so another `discovered` cell moves nothing and a genuinely orthogonal
family raises the ceiling itself. These seven are the only named, costed routes to that.

AND IT IS FREE TO TRY. `gate_policy` charges a FIXED 597 trials with a FIXED variance-of-Sharpes,
so adding several hundred cells raises no other candidate's bar (pinned by
test_the_trial_charge_is_fixed_and_never_taxes_breadth). Under the old batch-scaled charge this
sweep would have made every existing candidate harder to certify, which is precisely why it was
never run.

WHAT IS SWEPT AND WHAT IS NOT. Only families whose inputs the desk ALREADY HOLDS are emitted. A
family blocked on an input it does not have is listed in `BLOCKED` with the reason, because a cell
built without its input is not a test of the mechanism -- it is a test of the fallback, and it
would fail for a reason that says nothing about the hypothesis. That distinction is the whole
difference between a gap being measured and a gap being papered over.

NO PERFORMANCE IS CLAIMED on any emitted row: n=0 and every metric null. The gauntlet attaches the
only numbers that will ever attach.

    python desks/mt5/research/breadth_sweep.py [--apply] [--family vol_transition]
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
UNIVERSE = DESK / "data" / "universe"
CERTIFICATES = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"

#: FAMILIES WHOSE INPUTS THE DESK ALREADY HOLDS, with the grid each is swept over.
#:
#: The grids are deliberately coarse. A wide grid is not a better search -- it is the same search
#: with more ways to fit, and the deflated-Sharpe bar does not care how hard you looked. Each axis
#: here is one the family's own docstring names as mechanically meaningful, not every knob it has.
READY: dict[str, dict] = {
    # Price only. The board says "needs: price only", so there was never a blocker.
    "vol_transition": {
        "why": "the moment realised vol expands out of compression -- fires when breakouts stall, "
               "which is the failure regime of the family that dominates the book",
        "grid": [
            {"fast": f, "slow": s, "ratio_in": r, "rr": rr, "ttl_bars": 24, "atr_n": 20}
            for f, s in ((12, 96), (24, 192))
            for r in (1.4, 1.8)
            for rr in (1.5, 2.5)
        ],
    },
    # MEASURED 2026-09-12: _cot_frame('XAUUSD') returns 1,392 weekly observations from
    # data/cot_zcache.parquet -- 8,416 rows over 11 symbols, 2000-01-03 to 2026-09-01. Twenty-six
    # years of point-in-time positioning, with the Friday release lag already applied by the
    # loader. The board read BLOCKED on "COT net positioning" while the desk had owned the series
    # for the whole time; what was missing was cells.
    "cot_positioning": {
        "why": "weekly speculative positioning at multi-year extremes -- a clock no intraday "
               "family observes, so its errors have no reason to correlate with the book",
        "symbols": ("XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD", "EURUSD", "GBPUSD",
                    "AUDUSD", "USDJPY", "USDCHF", "USDCAD", "XTIUSD"),
        "grid": [
            {"lookback_weeks": w, "extreme_pct": p, "rr": rr, "ttl_bars": 240, "atr_n": 20}
            for w in (104, 156)
            for p in (0.85, 0.90, 0.95)
            for rr in (2.0,)
        ],
    },
    # MEASURED: _macro_series returns 27,793 observations -- a trailing percentile rank of the
    # broad trade-weighted dollar (DTWEXBGS) off data/fred_macro.json, lagged one publication day
    # and ranked only against its own past. Also never blocked.
    "macro_conditional": {
        "why": "a dollar-state condition changes WHEN other sleeves should fire rather than "
               "adding another directional signal",
        "grid": [
            {"regime_high": h, "side_in_high": s, "rr": rr, "ttl_bars": 96, "atr_n": 20}
            for h in (0.5, 0.7)
            for s in (1, -1)
            for rr in (2.0,)
        ],
    },
    # MEASURED: _tape_series returns a spread AND a flow series for every symbol tried. The tape
    # is the desk's own moat recording -- proprietary data nobody else holds, which is the one
    # axis whose errors cannot correlate with anything mined from a public source.
    "liquidity_regime": {
        "why": "fade dislocations made into an abnormally wide book -- an execution-derived edge "
               "off the desk's OWN tape, structurally independent of every price-only family",
        "grid": [
            {"lookback": lb, "widen_z": z, "rr": rr, "ttl_bars": 12, "atr_n": 20}
            for lb in (96, 192)
            for z in (1.5, 2.0, 2.5)
            for rr in (1.5,)
        ],
    },
    "orderflow_imbalance": {
        "why": "the flow half of the same tape -- a second, differently-conditioned read of "
               "proprietary microstructure",
        "grid": [
            {"lookback": lb, "z_in": z, "rr": rr, "ttl_bars": 12}
            for lb in (96, 192)
            for z in (1.5, 2.5)
            for rr in (1.5, 2.0)
        ],
    },
    # MEASURED: _event_index() returns 57 dated events, and the crash guard fixed earlier today
    # means a family handed an empty or index-like `events` now refuses instead of taking the
    # sweep down.
    "event_reaction": {
        "why": "a scheduled-release clock -- entirely different timing from any bar-structure "
               "family, which is what makes it an independent bet rather than another one",
        "grid": [
            {"mode": m, "side": s, "clock": "utc", "rr": 2.0, "ttl_bars": 24, "atr_n": 20}
            for m in ("drift", "fade")
            for s in (1, -1)
        ],
    },
    # MEASURED: _bars('EURUSD','H1') returns 37,366 bars, so a peer leg loads. The gauntlet's
    # build path already pops `peer_symbol` and hands the family a `peer` frame.
    "relative_value": {
        "why": "a cross-pair residual profits when direction does not, so it is uncorrelated "
               "with every directional family by construction rather than by measurement",
        "pairs": (("EURUSD", "GBPUSD"), ("AUDUSD", "NZDUSD"), ("USDCHF", "EURCHF"),
                  ("XAUUSD", "XAGUSD"), ("USDCAD", "XTIUSD"), ("EURJPY", "GBPJPY")),
        # WIDENED 2026-11-24 (docket supply): every same-peer-class pair of instruments the
        # sweep holds bars for (`class_pairs`), after the six named ones. A residual between two
        # members of ONE class (two USD legs, two indices, two crypto CFDs) is the family's own
        # construction; across classes it is cross_asset_residual's job, so none are minted.
        "class_pairs": True,
        "grid": [{"lookback": lb, "entry_z": z, "rr": 1.5, "ttl_bars": 48}
                 for lb in (96, 240) for z in (2.0, 2.5)],
    },
    # Same loader, more legs: the build path pops `factor_symbols` and hands over a list.
    "cross_asset_residual": {
        "why": "metals against FX against index after the common factor -- what is left when the "
               "shared driver is removed is the least correlated thing the desk can hold",
        "factor_sets": (("XAUUSD", ("EURUSD", "US500", "UST10Y")),
                        ("XTIUSD", ("USDCAD", "US500", "XAUUSD")),
                        ("XAGUSD", ("XAUUSD", "US500", "EURUSD")),
                        ("NAS100", ("US500", "UST10Y", "EURUSD"))),
        "grid": [{"lookback": lb, "entry_z": z, "rr": 1.5, "ttl_bars": 48}
                 for lb in (120, 240) for z in (2.0, 2.5)],
    },
}

#: Families still genuinely blocked. EMPTY as of 2026-09-12: every loader the gauntlet's build
#: path uses was tested and every one returned data -- cot 1,392 obs, macro 27,793, events 57,
#: tape spread/flow on every symbol tried, peer bars 37,366. The breadth board had been reporting
#: seven families BLOCKED on inputs the desk already held. What was actually missing, in every
#: single case, was CELLS IN THE DOCKET.
BLOCKED: dict[str, str] = {}

#: Instruments to sweep. THE LIQUID CORE, not the whole registry: a mechanism that cannot be found
#: on the majors and metals is not going to be rescued by an exotic cross, and 267 symbols x a
#: parameter grid is a docket nobody can converge. Restricted further to symbols that actually
#: have H1 bars on disk, because a cell with no bars is UNMEASURED rather than tested.
CORE = ("XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF",
        "NZDUSD", "EURJPY", "GBPJPY", "EURGBP", "AUDJPY", "XTIUSD", "NAS100", "US500",
        "US30", "GER40", "UK100", "JPN225", "BTCUSD", "ETHUSD")
#: EXOTIC FX IS BANNED (principal, 2026-11-24: no mining, judging or trading of exotic FX). USDZAR
#: and USDMXN left CORE that day, and `_with_bars` drops every symbol MetaTrader's registry classes
#: as an exotic (`exotic_cost_bar.exotic_symbols`' rule: the class name, never a hand list), so the
#: hypothesis-lane extras and every pair/factor leg below are exotic-free too.


#: EVERY CHART THE DESK HOLDS BARS FOR (principal 2026-09-16: "all breadth, all charts, all
#: sessions, not tons of H1"). A cell is emitted on a chart only when that symbol's bars for it
#: are on disk; H1 keeps the bare identity every existing cell has, the others carry
#: `timeframe`, which is the chart to load and stays in the cell's identity.
CHARTS = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")
#: THE SESSION AXIS (principal 2026-09-16: "all sessions maximised fully for true 24/7 trading").
#: `family_call.SESSIONS` defines the windows in server hours and applies the filter in the one
#: call path the gauntlet, the forward clock and the live executor share; here it is only an
#: identity key on the cell. Daily bars carry no session.
SESSION_AXIS = ("all", "asia", "london", "ny")
#: Constructors that are not families of their own: they take a spec and build others.
NOT_A_FAMILY = frozenset({"generic", "formula", "ensemble", "cross_sectional"})
#: How many new cells one run may merge, most intraday first: the sweep is idempotent, so a
#: docket of every family on every chart in every session fills over a few hourly runs rather
#: than in one write the gauntlet then has to load whole.
#:
#: MEASURED AGAINST THE SUPPLY TARGET, 2026-11-24 (reports/research/DOCKET_SUPPLY_CAPS): 40,000 an
#: hour is 960,000 a day -- 9.6x the 100k/day first-verdict target and above the judge's measured
#: ~420k/day build capacity -- so it is NOT what holds supply down; the exhausted grid was. It is
#: kept as the drain rate of the widened grid below (the docket every reader loads grows at most
#: this much an hour) and every cell it defers is billed as a missed-growth line in
#: BREADTH_SWEEP.json. `BREADTH_MAX_NEW_PER_RUN` overrides it on a box that measures otherwise.
MAX_NEW_PER_RUN = int(os.environ.get("BREADTH_MAX_NEW_PER_RUN", "40000") or 40000)


def _with_bars() -> list[str]:
    """Instruments to sweep: the liquid core plus every instrument in the hypothesis lane that
    has H1 bars on disk -- the same breadth the discovery hunt had (principal 2026-09-16), now
    spent on the families that are not banned."""
    have = {p.name.split("_")[0].upper() for p in UNIVERSE.glob("*_H1.parquet")}
    out = [s for s in CORE if s in have and not is_exotic(s)]
    try:
        from research.universe_policy import may_hypothesise
        extra = sorted(s for s in have
                       if s not in out and may_hypothesise(s) and not is_exotic(s))
        out.extend(extra)
    except Exception:
        pass
    return out


def is_exotic(symbol: str) -> bool:
    """True when MetaTrader's registry classes `symbol` as an exotic (the class name, read through
    `universe_policy.asset_class_of`, never a symbol list). An unreadable registry answers False
    here, and such a symbol is still UNCLASSIFIED to `may_hypothesise`, so it is swept only when
    it is literally in CORE -- which holds no exotic."""
    try:
        from research.universe_policy import asset_class_of
        return "exotic" in str(asset_class_of(symbol) or "").lower()
    except Exception:
        return False


def _equities_with_bars() -> list[str]:
    """Share CFDs with H1 bars: hypothesis-eligible ONLY for the cross-sectional class books
    (`universe_policy.CROSS_SECTIONAL_FAMILIES`, principal amendment 2026-09-30)."""
    have = {p.name.split("_")[0].upper() for p in UNIVERSE.glob("*_H1.parquet")}
    try:
        from research.universe_policy import is_equity
        return sorted(s for s in have if is_equity(s))
    except Exception:
        return []


def _charts_for(sym: str) -> list[str]:
    return [tf for tf in CHARTS if (UNIVERSE / f"{sym}_{tf}.parquet").exists()]


def _sessions_for(tf: str) -> tuple[str, ...]:
    return ("all",) if tf == "D1" else SESSION_AXIS


def _session_slots(family: str, base: dict, tf: str,
                   symbol: str) -> list[tuple[dict, dict | None]]:
    """(params, remap note) per session slot on chart `tf`. A slot whose window the family can
    never fire in is minted as the firing-hours oracle's stand-in (re-anchored hour params, or
    re-homed to where it fires) -- one cell per slot, so the sweep mints exactly as many cells as
    before; an UNMEASURED family keeps the plain axis (`libs/research/family_firing.py`)."""
    axis = _sessions_for(tf)
    try:
        from libs.research import family_firing
        return [(p, remap) for _s, p, remap in
                family_firing.session_cells(family, base, axis, symbol=symbol)]
    except Exception:
        return [({**base, **({"session": s} if s != "all" else {})}, None) for s in axis]


def _remapped(cell: dict, remap: dict | None) -> dict:
    if remap:
        cell["session_remap"] = remap
    return cell


def _banned(family: str) -> bool:
    try:
        from research.family_policy import family_banned
        return bool(family_banned(family))
    except Exception:
        return False


def default_families() -> tuple[dict[str, str], dict[str, str]]:
    """(sweepable, blocked): EVERY registered family the desk can call on bars alone, with its
    default parameters, and the ones it cannot with the reason (principal 2026-09-16: "make them
    hunt every family ever and anything which isn't discovery").

    A family is sweepable at its defaults when every argument beyond the bars and the side has a
    default. One that REQUIRES an input (a peer, factors, a COT frame, a tape series) is blocked
    here and swept only through the READY grid that names that input; the banned family and the
    spec-driven constructors are set aside by name.
    """
    import inspect
    try:
        from mt5desk import families as fam_mod
        from mt5desk import families_orthogonal as fo
    except Exception as exc:                                     # pragma: no cover
        return {}, {"*": f"families unimportable ({type(exc).__name__}: {exc})"}
    names: dict[str, Any] = {}
    for name, entry in getattr(fam_mod, "FAMILY_REGISTRY", {}).items():
        fn = entry.get("func") if isinstance(entry, dict) else entry
        if callable(fn):
            names[str(name)] = fn
    for name, fn in getattr(fo, "ORTHOGONAL_FAMILIES", {}).items():
        names.setdefault(str(name), fn)
    ok: dict[str, str] = {}
    blocked: dict[str, str] = {}
    for name, fn in sorted(names.items()):
        if name in READY:
            continue
        if name in NOT_A_FAMILY:
            blocked[name] = "a constructor that builds families from a spec, not a family"
            continue
        if _banned(name):
            blocked[name] = "banned (data/banned_families.json)"
            continue
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            blocked[name] = "signature unreadable"
            continue
        params = list(sig.parameters.values())[1:]
        need = [p.name for p in params
                if p.default is inspect.Parameter.empty and p.name != "side"
                and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)]
        if need:
            blocked[name] = f"requires input(s) {need} the sweep cannot name at defaults"
            continue
        ok[name] = "default parameters, every chart, every session"
    return ok, blocked


def _tf_rank(tf: str) -> int:
    return 0 if tf in ("M1", "M5", "M15", "M30") else (1 if tf == "H4" else 2)


def _targets(fam: str, spec: dict, syms: list[str]) -> list[tuple[str, dict]]:
    """(symbol, extra params) the family should be swept over.

    Three shapes, because three families need a partner leg named in the SPEC rather than
    inferred: `pairs` for a peer, `factor_sets` for several factors, `symbols` to restrict a
    family to the instruments its input actually covers (COT has 11, not 24 -- sweeping the other
    13 would build cells whose input is None and fail them for a reason that says nothing).
    """
    if spec.get("pairs"):
        pairs = list(spec["pairs"])
        if spec.get("class_pairs"):
            pairs += [p for p in class_pairs(syms) if p not in pairs]
        return [(a, {"peer_symbol": b}) for a, b in pairs
                if a in syms and not is_exotic(a) and not is_exotic(b)]
    if spec.get("factor_sets"):
        return [(a, {"factor_symbols": list(f)}) for a, f in spec["factor_sets"]
                if a in syms and not is_exotic(a) and not any(is_exotic(x) for x in f)]
    allowed = spec.get("symbols")
    pool = [s for s in syms if (not allowed or s in allowed)]
    return [(s, {}) for s in pool]


#: Peer classes whose members are paired for `relative_value` (universe_policy.peer_class). The
#: `equity` class is absent: relative_value is not one of the cross-sectional families a share
#: CFD may be hunted in.
PAIR_CLASSES = ("fx_usd", "fx_cross", "index", "commodity", "bond", "crypto")


def class_pairs(syms: list[str]) -> list[tuple[str, str]]:
    """Every (a, b), a < b, of two non-exotic `syms` in the same peer class, sorted."""
    try:
        from research.universe_policy import peer_class
    except Exception:
        return []
    by: dict[str, list[str]] = {}
    for sym in syms:
        if is_exotic(sym):
            continue
        try:
            klass = peer_class(sym)
        except Exception:
            klass = None
        if klass in PAIR_CLASSES:
            by.setdefault(str(klass), []).append(sym)
    out: list[tuple[str, str]] = []
    for klass in PAIR_CLASSES:
        members = sorted(set(by.get(klass, [])))
        out += [(a, b) for i, a in enumerate(members) for b in members[i + 1:]]
    return out


#: What the last `cells()` call set aside as UNTESTABLE, by `family|chart|verdict`, and why. A
#: count the report publishes -- a refusal only the sweep knows about is one nobody acts on.
LAST_SET_ASIDE: dict[str, dict[str, Any]] = {}
REPORT = DESK / "reports" / "BREADTH_SWEEP.json"


def _testable(fam: str, p: dict) -> bool:
    """TESTABLE BY THE SEALED GAUNTLET, or set aside by name (principal 2026-09-30: "testable").

    Two things made a cell here untestable while it still spent a docket row and a judge slot:
    a chart the family DECLARES it cannot express (`families_orthogonal.FAMILY_TIMEFRAMES` --
    `relative_value` on M5 measures quoting hours, `clock_transition` on D1 has no stamp hour to
    gate on), and a family whose data input the sealed `build_cell` never loads or hands in a
    shape the family cannot read (`research/gauntlet_buildability`, measured by building real
    cells). Either way the family returns no signals and the judge files a market "no" that the
    market never gave. This file's own rule already says it: a cell built without its input is a
    test of the fallback, not of the mechanism.

    Refusal is counted per (family, chart, verdict) with the reason, never silent, and an
    unimportable probe refuses NOTHING (L1.28a: a missing measurement is not a verdict).
    """
    try:
        from research.gauntlet_buildability import BUILDABLE, cell_verdict
    except Exception:
        return True
    verdict, why = cell_verdict(fam, p)
    if verdict == BUILDABLE:
        return True
    key = f"{fam}|{p.get('timeframe') or 'H1'}|{verdict}"
    row = LAST_SET_ASIDE.setdefault(key, {"family": fam, "chart": p.get("timeframe") or "H1",
                                          "verdict": verdict, "why": why, "cells": 0})
    row["cells"] += 1
    return False


def _certified_family_counts() -> dict[str, int]:
    """Actual canonical certificates, never miner claims or raw candidate counts."""
    try:
        doc = json.loads(CERTIFICATES.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    rows = doc.get("survivors") if isinstance(doc, dict) else None
    if not isinstance(rows, dict):
        return {}
    counts: dict[str, int] = {}
    for cert in rows.values():
        if not isinstance(cert, dict):
            continue
        fam = str((cert.get("shadow_spec") or {}).get("family") or cert.get("family") or "")
        if fam:
            counts[fam] = counts.get(fam, 0) + 1
    return counts


def _orthogonal_key() -> Any:
    """Spend a capped merge on intraday, under-certified families, then least-judged pairs.

    No family is banned: a genuinely distinct variant may still pass the full unchanged gates.
    This only prevents a cap from being exhausted by another copy of a saturated mechanism
    before an uncultivated family reaches the same evaluator.
    """
    try:
        from research.breadth_rotation import judged_counts
        _by_sym, by_pair = judged_counts()
    except Exception:
        by_pair = {}
    certified = _certified_family_counts()

    def key(r: dict) -> tuple:
        tf = str((r.get("params") or {}).get("timeframe") or "H1")
        fam = str(r["family"])
        return (_tf_rank(tf), certified.get(fam, 0),
                by_pair.get((str(r["symbol"]).upper(), fam), 0),
                r["symbol"], r["family"])
    return key


def cells(only: str | None = None) -> list[dict]:
    now = datetime.now(tz=UTC).isoformat()
    syms = _with_bars()
    out: list[dict] = []
    LAST_SET_ASIDE.clear()
    for fam, spec in READY.items():
        if only and fam != only:
            continue
        if _banned(fam):
            continue
        for sym, extra in _targets(fam, spec, syms):
            for params in spec["grid"]:
                for tf in _charts_for(sym) or ["H1"]:
                    base = dict(params)
                    base.update(extra)
                    if tf != "H1":
                        base["timeframe"] = tf
                    for p, remap in _session_slots(fam, base, tf, sym):
                        if _testable(fam, p):
                            out.append(_remapped(_cell(sym, fam, p, spec, now), remap))
    sweepable, _blocked = default_families()
    for fam, why in sweepable.items():
        if only and fam != only:
            continue
        spec = {"why": f"every family, {why}"}
        for sym in syms:
            for tf in _charts_for(sym) or ["H1"]:
                base: dict = {} if tf == "H1" else {"timeframe": tf}
                for p, remap in _session_slots(fam, base, tf, sym):
                    if _testable(fam, p):
                        out.append(_remapped(_cell(sym, fam, p, spec, now), remap))
    # Most intraday first, so a capped merge reaches the charts the principal ranked highest; then
    # least-judged (symbol, family) first, so the cap spends itself on orthogonal ground.
    out.sort(key=_orthogonal_key())
    # THEN THE FAILURE MEMORY (Tier S S13): inside each chart tier, cells in a neighbourhood the
    # memory has already mapped as dead go LAST and carry the theorem that maps it.
    out, stats = order_by_failure_memory(out)
    FAILURE_MEMORY_STATS.clear()
    FAILURE_MEMORY_STATS.update(stats)
    return out


# =============================================================================================
# THE PARAMETER-VARIANT AXIS (2026-11-24, docket supply >= 100k new cells a day).
#
# THE DEFECT. Every default family above is swept at ONE parameter point per (symbol, chart,
# session). That grid is finite and was minted out within days of 2026-09-16, so on every later
# pass this sweep added ~0 cells: the judge could build 300-420k cells a day and received ~6.3k
# never-judged ones (JUDGE_100K_ROOT_CAUSE_2026-11-24). The supply was bounded by the grid, not by
# MAX_NEW_PER_RUN.
#
# THE WIDENING, STRUCTURE-PRESERVING BY CONSTRUCTION. A variant never moves one knob against the
# others (a fast EMA past its slow one, an oversold above its overbought). It applies two joint
# moves, read off the family's OWN signature defaults:
#   * TIME SCALE: every length parameter (lookbacks, windows, holds, ttl, lags) scaled together by
#     one factor -- the same rule run faster or slower, every ordering between lengths kept;
#   * PAYOFF: the reward:risk `rr` scaled -- the same entry with a nearer or farther target.
# Hours, minutes, weekdays, sides, signs, modes, quantiles and multipliers are never touched: they
# are calendar or categorical, and scaling them is not a variant of the rule, it is another rule.
#
# EVERY VARIANT IS BUILDABLE OR IT IS NOT MINTED: `_testable` (gauntlet_buildability.cell_verdict,
# the sealed build_cell's own lookups, its chart refusals and its required-parameter check) runs
# on every cell, a chart with no bars on disk is never offered, and a variant only ever carries
# keys that are in the family's signature, so the judge's call binds exactly as it does at the
# defaults. NO GATE MOVES: the trial charge is the fixed 597 (`gate_policy`), FDR is untouched,
# and nothing here screens on performance.
# =============================================================================================

#: Joint time-scale factors for a family's length parameters.
TIME_SCALES: tuple[float, ...] = (0.5, 0.75, 1.5, 2.0)
#: Factors for the reward:risk target.
RR_SCALES: tuple[float, ...] = (0.6, 1.5)
#: A length parameter, by name.
_LENGTH = re.compile(r"(^n$|_n$|lookback|window|_bars$|^bars$|_d$|_days$|period|channel|ema|"
                     r"fast|slow|^norm$|^lag$|_lag$|stride|^z_obs$|cooldown|^mom_n$)")
#: Never a length, whatever else the name says: calendar, categorical or a multiplier.
_NOT_LENGTH = re.compile(r"(hour|minute|_min$|start|end|dow|side|sign|direction|mode|seed|"
                         r"decision|stale|skip|quantile|mult|_pct$|_q$)")
#: Where the walk resumes next pass, so each pass mints NEW cells and never re-walks the minted.
VARIANT_CURSOR = DESK / "data" / "hypotheses" / "breadth_variant_cursor.json"
#: THE WALK'S PACE, sized off two measured numbers rather than a round one. The widened grid is a
#: STOCK of ~1.4M never-judged cells on the box (88 non-exotic hypothesis instruments x 65 families
#: x their variant points x charts x sessions; DOCKET_SUPPLY_CAPS_2026-11-24), not a flow. Drained
#: at MAX_NEW_PER_RUN it would land in ~36 h and double a docket every reader loads whole; paced at
#: twice the 100k/day first-verdict target (SUPPLY_TARGET_PER_DAY) it stays inside the judge's
#: measured 300-420k/day build capacity, so every cell minted can be judged the day it lands, and
#: the stock lasts about a week. When the pace binds, the cells it leaves are a missed-growth line.
SUPPLY_TARGET_PER_DAY = 100_000
VARIANT_PER_RUN = int(os.environ.get("BREADTH_VARIANT_PER_RUN", "")
                      or -(-2 * SUPPLY_TARGET_PER_DAY // 24))
#: Wall clock the walk may spend: half of the leg's 720 s (hourly_cycle SEARCH_BUDGET_SEC), so the
#: docket write and the report always land inside the leg. A stop moves the cursor, never a cell.
VARIANT_BUDGET_S = float(os.environ.get("BREADTH_VARIANT_BUDGET_S", "360") or 360)


def _is_length(name: str, default: Any) -> bool:
    return (isinstance(default, int) and not isinstance(default, bool) and default >= 1
            and bool(_LENGTH.search(name)) and not _NOT_LENGTH.search(name))


def _family_defaults(family: str) -> dict[str, Any]:
    """The family's own keyword defaults beyond the bars and the side; {} when unreadable."""
    try:
        from research.gauntlet_buildability import _family_table
        fn = _family_table().get(family)
        params = list(inspect.signature(fn).parameters.values())[1:] if fn else []
    except Exception:
        return {}
    return {p.name: p.default for p in params
            if p.default is not inspect.Parameter.empty and p.name != "side"
            and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)}


def _scale_length(v: int, k: float) -> int:
    return max(2 if v >= 2 else 1, round(v * k))


def param_variants(family: str, defaults: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """The family's variant points, each as ONLY the keys that differ from its defaults.

    Rank 0 is the default point itself ({}). Deterministic; duplicates (a scale that rounds back
    to the defaults) collapse."""
    d = _family_defaults(family) if defaults is None else dict(defaults)
    lengths = {k: v for k, v in d.items() if _is_length(k, v)}
    rr = d.get("rr")
    has_rr = isinstance(rr, (int, float)) and not isinstance(rr, bool) and rr > 0
    out: list[dict[str, Any]] = [{}]
    seen = {"{}"}
    for k_t in (1.0, *TIME_SCALES):
        for k_r in (1.0, *RR_SCALES):
            if (k_t != 1.0 and not lengths) or (k_r != 1.0 and not has_rr):
                continue
            v: dict[str, Any] = {}
            if k_t != 1.0:
                for name, val in lengths.items():
                    new = _scale_length(int(val), k_t)
                    if new != val:
                        v[name] = new
            if k_r != 1.0 and has_rr:
                new_rr = round(float(rr) * k_r, 2)
                if new_rr != rr:
                    v["rr"] = new_rr
            key = json.dumps(v, sort_keys=True)
            if key not in seen:
                seen.add(key)
                out.append(v)
    return out


def _read_cursor(path: Path | None = None) -> int:
    try:
        doc = json.loads((path or VARIANT_CURSOR).read_text("utf-8"))
        return max(0, int(doc.get("next", 0)))
    except (OSError, ValueError, TypeError, AttributeError):
        return 0


def write_cursor(state: dict[str, Any], path: Path | None = None) -> None:
    target = path or VARIANT_CURSOR
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, indent=1), encoding="utf-8")
        tmp.replace(target)
    except OSError:
        pass


class VariantWalk:
    """Mints never-seen variant cells in a fixed order, resuming at a durable cursor.

    The order is (variant rank, chart tier, chart, family, symbol): every family's first variant
    on every instrument before anyone's second, intraday charts first within a rank -- so any
    prefix a capped pass reaches is family- and instrument-balanced. Called with the docket's own
    identity set and the room left under MAX_NEW_PER_RUN; it adds what it mints to that set."""

    def __init__(self, families: list[str], syms: list[str], *,
                 equities: list[str] | None = None, cursor: int | None = None,
                 budget_s: float | None = None, per_run: int | None = None) -> None:
        self.per_run = VARIANT_PER_RUN if per_run is None else int(per_run)
        self.variants = {f: param_variants(f) for f in sorted(families)}
        self.syms = list(syms)
        self.equities = list(equities or [])
        self.start = _read_cursor() if cursor is None else int(cursor)
        self.budget_s = VARIANT_BUDGET_S if budget_s is None else float(budget_s)
        self.next = self.start
        self.stats: dict[str, Any] = {"minted": 0, "already_in_docket": 0, "set_aside": 0,
                                      "wrapped": False, "budget_hit": False, "room": 0,
                                      "positions": 0}
        self._charts: dict[str, list[str]] = {}

    def _targets(self, family: str) -> list[str]:
        try:
            from research.universe_policy import CROSS_SECTIONAL_FAMILIES
        except Exception:
            return self.syms
        return self.syms + self.equities if family in CROSS_SECTIONAL_FAMILIES else self.syms

    def _charts_of(self, sym: str) -> list[str]:
        if sym not in self._charts:
            self._charts[sym] = _charts_for(sym) or ["H1"]
        return self._charts[sym]

    def positions(self) -> list[tuple[int, str, str, str]]:
        """(rank, chart, family, symbol), in walk order. Rank 0 (defaults) is walked too: it is
        the only door a share CFD's class book has into this sweep, and for every other symbol
        `cells()` already minted it, so the docket identity skips it at no stamping cost."""
        charts = sorted(CHARTS, key=lambda tf: (_tf_rank(tf), CHARTS.index(tf)))
        top = max((len(v) for v in self.variants.values()), default=0)
        out = []
        for rank in range(top):
            for tf in charts:
                for fam, vs in self.variants.items():
                    if rank >= len(vs):
                        continue
                    for sym in self._targets(fam):
                        out.append((rank, tf, fam, sym))
        return out

    def __call__(self, seen: set[str], room: int, key: Any) -> list[dict]:
        room = min(int(room), max(0, int(self.per_run)))
        self.stats["room"] = int(room)
        if room <= 0 or not self.variants:
            return []
        pos = self.positions()
        self.stats["positions"] = len(pos)
        if not pos:
            return []
        now = datetime.now(tz=UTC).isoformat()
        t0 = time.monotonic()
        out: list[dict] = []
        n = len(pos)
        i = self.start % n
        for step in range(n):
            if len(out) >= room:
                break
            if time.monotonic() - t0 > self.budget_s:
                self.stats["budget_hit"] = True
                break
            rank, tf, fam, sym = pos[(i + step) % n]
            if (i + step) % n == n - 1:
                self.stats["wrapped"] = True
            self.next = (i + step + 1) % n
            if tf not in self._charts_of(sym):
                continue
            base = dict(self.variants[fam][rank])
            if tf != "H1":
                base["timeframe"] = tf
            spec = {"why": (f"every family at its parameter variant {rank} "
                            f"(joint time-scale / reward:risk move off its own defaults)")}
            for p, remap in _session_slots(fam, base, tf, sym):
                row = {"symbol": sym, "family": fam, "params": p}
                ident = key(row)
                if ident in seen:
                    self.stats["already_in_docket"] += 1
                    continue
                if not _testable(fam, p):
                    self.stats["set_aside"] += 1
                    continue
                cell = _remapped(_cell(sym, fam, p, spec, now), remap)
                cell["variant_rank"] = rank
                seen.add(ident)
                out.append(cell)
                if len(out) >= room:
                    break
        self.stats["minted"] = len(out)
        return out

    def state(self) -> dict[str, Any]:
        return {"next": int(self.next), "start": int(self.start),
                "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                "families": len(self.variants),
                "variant_points": sum(len(v) for v in self.variants.values()),
                "instruments": len(self.syms), "equities": len(self.equities),
                **self.stats}


def supply_missed_growth(walk_state: dict[str, Any] | None, added: int | None,
                         max_new: int) -> list[dict[str, Any]]:
    """The cap's missed-growth line (GROWTH GOVERNANCE: no cap without one). When the pass filled
    MAX_NEW_PER_RUN, the cells it left for the next pass are deferred research in their own units
    -- never dropped, the cursor holds their place -- and the E[log W] price is UNMEASURED."""
    now = datetime.now(tz=UTC)
    out: list[dict[str, Any]] = []
    ws = walk_state or {}
    if ws.get("room") and int(ws.get("minted") or 0) >= int(ws["room"]) and not ws.get("wrapped"):
        out.append({"day": now.date().isoformat(), "at": now.isoformat(timespec="seconds"),
                    "rail": "breadth_sweep.VARIANT_PER_RUN", "kind": "opportunity_cost",
                    "value": None, "verdict": "UNMEASURED",
                    "units": "variant cells deferred to the next pass",
                    "cap": int(ws["room"]), "added": int(ws.get("minted") or 0),
                    "cursor_next": ws.get("next"), "positions": ws.get("positions"),
                    "why": ("the variant walk minted its pace for this pass (2x the 100k/day "
                            "target, inside the judge's measured capacity); the rest of the "
                            "never-minted stock waits at the cursor, nothing is dropped")})
    if added is None or added < max_new:
        return out
    return [*out, {"day": now.date().isoformat(), "at": now.isoformat(timespec="seconds"),
             "rail": "breadth_sweep.MAX_NEW_PER_RUN", "kind": "opportunity_cost",
             "value": None, "verdict": "UNMEASURED", "units": "cells deferred to the next pass",
             "cap": int(max_new), "added": int(added),
             "cursor_next": (walk_state or {}).get("next"),
             "why": (f"the pass merged its cap of {max_new} new cell(s); the walk's remaining "
                     "never-minted cells wait at the cursor for the next hourly pass")}]


def write_report(new: list[dict], syms: list[str], added: int | None, total: int | None,
                 variants: dict[str, Any] | None = None) -> dict:
    """reports/BREADTH_SWEEP.json: what this pass minted, over what, and what it set aside.

    The sweep writes the docket directly rather than donating through the intake, so without
    this file no reader (`producer_breadth` first) could say which symbols, charts, sessions and
    families it covered -- a producer whose breadth cannot be read is UNMEASURED, not wide."""
    from collections import Counter
    doc = {
        "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "producer": "desks/mt5/research/breadth_sweep.py",
        "instruments_with_bars": len(syms),
        "cells_built": len(new),
        "cells_merged": added, "docket_rows": total, "max_new_per_run": MAX_NEW_PER_RUN,
        "symbols": sorted({str(r["symbol"]) for r in new}),
        "families": dict(sorted(Counter(str(r["family"]) for r in new).items())),
        "charts": dict(sorted(Counter(str((r.get("params") or {}).get("timeframe") or "H1")
                                      for r in new).items())),
        "sessions": dict(sorted(Counter(str((r.get("params") or {}).get("session") or "all")
                                        for r in new).items())),
        "set_aside_untestable": sorted(LAST_SET_ASIDE.values(),
                                       key=lambda r: (-int(r["cells"]), r["family"])),
        "set_aside_cells": sum(int(r["cells"]) for r in LAST_SET_ASIDE.values()),
        "exotics_excluded": "principal 2026-11-24: registry class 'exotic' never swept",
        "variant_walk": variants,
        "rule": ("a cell the sealed gauntlet cannot build with its inputs, or on a chart its "
                 "family "
                 "declares it cannot express, is set aside BY NAME and counted here -- never "
                 "minted to be judged as a market 'no' the market never gave"),
    }
    try:
        prev = json.loads(REPORT.read_text("utf-8"))
        lines = list(prev.get("missed_growth") or []) if isinstance(prev, dict) else []
    except (OSError, ValueError):
        lines = []
    lines += supply_missed_growth(variants, added, MAX_NEW_PER_RUN)
    doc["missed_growth"] = lines[-50:]
    try:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        tmp = REPORT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        tmp.replace(REPORT)
    except OSError as exc:
        doc["write_error"] = f"{type(exc).__name__}: {exc}"
    return doc


#: what the last `cells()` call did with the failure memory (printed by `main`)
FAILURE_MEMORY_STATS: dict = {}


def _cell_tf_rank(r: dict) -> int:
    return _tf_rank(str((r.get("params") or {}).get("timeframe") or "H1"))


def order_by_failure_memory(rows: list[dict], memory: dict | None = None) -> tuple[list[dict],
                                                                                  dict]:
    """Consult `libs/tiers/failure_memory` -- the theorems `tier_s.organ_failure_memory` compresses
    hourly from the gate ledger, the forward clocks and the live fills -- and push the cells it
    already maps as dead behind the rest of their chart tier, tagged with the theorem.

    REORDER, NEVER FILTER (the standing order: raw cell mining is never reduced). Every cell is
    still returned and still merged; the only thing that moves is which cells a capped run reaches
    FIRST, so unexplored ground is judged before re-litigated ground. The neighbourhood key is the
    one the memory is built on -- (mechanism from `axis_registry`, asset class from
    `universe_policy`, session) -- the same key `tier_s._explored` orders its own emissions by.
    A suspended organ (`libs/tiers/authority`) and an absent or stale memory both leave the order
    exactly as it was."""
    from libs.tiers import failure_memory as fm
    try:
        from libs.tiers import authority
        if authority.suspended("failure_memory"):
            return rows, {"consulted": False, "why": "failure_memory organ suspended",
                          "rows": len(rows), "tagged": 0, "moved": 0}
    except Exception:
        pass
    mem = fm.load() if memory is None else memory
    mech: dict[str, str] = {}
    acls: dict[str, str] = {}

    def desc_of(r: dict) -> dict:
        fam, sym = str(r.get("family") or ""), str(r.get("symbol") or "")
        if fam not in mech:
            try:
                import axis_registry
                mech[fam] = str(axis_registry.classify_family(fam)[0])
            except Exception:
                mech[fam] = fam or "UNKNOWN"
        if sym not in acls:
            try:
                import universe_policy
                acls[sym] = str(universe_policy.asset_class_of(sym))
            except Exception:
                acls[sym] = "UNCLASSIFIED"
        return {"mechanism": mech[fam], "asset_class": acls[sym],
                "selector": str((r.get("params") or {}).get("session") or "?")}

    return fm.prioritise(rows, mem, desc_of, rank=_cell_tf_rank)


def _cell(sym: str, fam: str, p: dict, spec: dict, now: str) -> dict:
    """One docket row: the executable spec and nothing claimed about it."""
    from libs.data.pit import stamp

    return stamp({
        "symbol": sym, "family": fam, "params": p,
        "n": 0, "exp_r": None, "max_dd_r": None, "t_stat": None,
        "profit_factor": None, "win_rate": None,
        "source": f"breadth_sweep/{fam}",
        "url": None,
        "producer": "desks/mt5/research/breadth_sweep.py",
        "first_seen": now, "pit_stamp": now,
        "why": (f"closing a NAMED breadth gap: {spec['why']}. No performance is "
                f"claimed -- the gauntlet attaches the only numbers that attach."),
    }, "breadth_sweep", now=datetime.fromisoformat(now))


def apply(new: list[dict], max_new: int = MAX_NEW_PER_RUN,
          extra: Any = None) -> tuple[int, int]:
    """Merge, deduped on the executable spec, at most `max_new` per run (the input order is
    most-intraday-first), so a daily clock cannot grow the docket without bound and one run
    never hands the gauntlet a docket it has to load whole.

    `extra(seen, room, key)` (the VariantWalk) fills whatever room `new` leaves, against the
    same docket identity set, so its cells are never-seen by construction."""
    from research.job_lock import exclusive_job

    with exclusive_job("merge_hypotheses", need_mb=14000) as owned:
        if not owned:
            raise RuntimeError("Canonical docket writer lane or memory admission refused")
        return _apply_locked(new, max_new, extra)


def _apply_locked(new: list[dict], max_new: int, extra: Any = None) -> tuple[int, int]:
    try:
        docket = json.loads(DOCKET.read_text(encoding="utf-8"))
    except FileNotFoundError:
        docket = []
    if not isinstance(docket, list):
        raise SystemExit(f"{DOCKET} is not a list; refusing to overwrite a docket I cannot read")

    def key(r: dict) -> str:
        return json.dumps([r.get("symbol") or r.get("sym"), r.get("family"), r.get("params") or {}],
                          sort_keys=True, default=str)

    seen = {key(r) for r in docket if isinstance(r, dict)}
    add = []
    for row in new:
        ident = key(row)
        if ident not in seen and len(add) < max(0, int(max_new)):
            add.append(row)
            seen.add(ident)
    if extra is not None and len(add) < max(0, int(max_new)):
        add.extend(extra(seen, max(0, int(max_new)) - len(add), key))
    if add:
        from libs.data.pit import stamp_or_refuse
        from research.merge_hypotheses import _write_docket_atomically

        add, refused = stamp_or_refuse(add, "breadth_sweep")
        if refused:
            raise ValueError(f"Breadth sweep refused {len(refused)} unstamped candidates")
        docket.extend(add)
        _write_docket_atomically(DOCKET, docket)
    return len(add), len(docket)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--family", default=None, help="sweep one ready family only")
    a = ap.parse_args(argv)
    syms = _with_bars()
    new = cells(a.family)
    print(f"breadth sweep: {len(new)} cell(s) over {len(syms)} instrument(s) with H1 bars")
    for fam, spec in READY.items():
        if a.family and fam != a.family:
            continue
        tg = _targets(fam, spec, syms)
        print(f"  READY   {fam:<22} {len(spec['grid'])} param set(s) x {len(tg)} target(s)")
    sweepable, blocked_default = default_families()
    print(f"  DEFAULT {len(sweepable)} more famil(ies) at their defaults: "
          f"{', '.join(sorted(sweepable))}")
    for fam, why in sorted(blocked_default.items()):
        print(f"  SET ASIDE {fam:<20} {why[:90]}")
    from collections import Counter
    by_tf = Counter(str((r.get('params') or {}).get('timeframe') or 'H1') for r in new)
    by_sess = Counter(str((r.get('params') or {}).get('session') or 'all') for r in new)
    print(f"  by chart {dict(by_tf)}; by session {dict(by_sess)}")
    fms = FAILURE_MEMORY_STATS
    if fms.get("consulted"):
        print(f"  failure memory: {fms.get('theorems')} theorem(s), {fms.get('rules')} rule(s); "
              f"{fms.get('tagged')} cell(s) in mapped-dead neighbourhoods tagged and moved to the "
              f"back of their chart tier ({fms.get('moved')} reordered, none dropped)")
    else:
        print(f"  failure memory: not consulted ({fms.get('why') or 'absent, stale or empty'})"
              " -- order unchanged")
    for fam, why in BLOCKED.items():
        print(f"  BLOCKED {fam:<22} {why[:96]}")
    if not BLOCKED:
        print("  BLOCKED (none) -- every loader the gauntlet uses was measured and returned data")
    if LAST_SET_ASIDE:
        n_aside = sum(int(r["cells"]) for r in LAST_SET_ASIDE.values())
        print(f"  SET ASIDE UNTESTABLE {n_aside} cell(s) over {len(LAST_SET_ASIDE)} "
              f"(family, chart) pair(s) -- see {REPORT.name}")
    walk = None
    if not a.family:
        walk = VariantWalk(list(sweepable), syms, equities=_equities_with_bars())
        print(f"  VARIANTS {sum(len(v) for v in walk.variants.values())} parameter point(s) "
              f"over {len(walk.variants)} famil(ies), resuming at cursor {walk.start}")
    if not a.apply:
        write_report(new, syms, None, None, walk.state() if walk else None)
        print("  --apply not given; nothing written to the docket")
        return 0
    added, total = apply(new, extra=walk)
    state = walk.state() if walk else None
    if walk is not None and state is not None:
        write_cursor(state)
        print(f"  variant walk: {state['minted']} new variant cell(s), "
              f"{state['already_in_docket']} already in the docket, {state['set_aside']} set "
              f"aside untestable; cursor {state['start']} -> {state['next']} of "
              f"{state['positions']}{' (budget hit)' if state['budget_hit'] else ''}")
    write_report(new, syms, added, total, state)
    print(f"  merged {added} new cell(s); docket now {total} row(s)")
    if not added:
        print("  (all already present -- the sweep is idempotent on the executable spec)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
