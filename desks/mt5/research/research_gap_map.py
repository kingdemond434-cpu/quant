"""THE RESEARCH GAP MAP -- every economically valid cell of the desk's search space, in ONE state.

WHY THIS EXISTS (ledger M21). `axis_registry` can say where the desk HAS been: it collects the
cells six sources have judged, certified, run forward or traded. What no artifact on this tree
could say is where the desk COULD have been and never went -- the ground that is admissible under
the ontology, has bars and has the observable the mechanism needs, and holds not one candidate.
A gap nobody can name is a gap nobody searches, and "we have covered that" has been an assumption
for as long as the coverage was never enumerated.

So: the eight axes of `registry.GRID_AXES` -- asset_class x mechanism x economic_actor x
information x chart x session x horizon x regime -- and exactly ONE state per cell, from evidence:

    LIVE          a LIVE or STANDBY sleeve sits there and carries capital
    FORWARD       a forward clock is accruing there
    SURVIVED      a certificate was minted there
    FAILED        the gauntlet judged it and it lost -- negative knowledge, which is knowledge
    TESTING       a candidate is queued, claimed, donated or on the docket for it
    READY         bars exist for that class on that chart and the mechanism's observable is
                  present -- the desk could test it today and has not
    DATA_MISSING  the mechanism's required observable is not on this box at all
    UNSEEN        nothing: no bars for that class on that chart, and no candidate either

PRECEDENCE IS STATED, NOT INFERRED, and it is EVIDENCE FIRST:
LIVE > FORWARD > SURVIVED > FAILED > TESTING > READY > DATA_MISSING > UNSEEN. A cell somebody
actually judged outranks a cell the box merely could judge, even when the observable is missing --
because what happened beats what is possible.

THE FULL PRODUCT OF THE EIGHT VOCABULARIES IS ASTRONOMICAL AND MOSTLY MEANINGLESS. 8 classes x 20
mechanisms x 9 information axes x 20 actors x 5 charts x 5 sessions x 4 horizons x 8 regimes is
over ten million coordinates, and almost none of them is a question anybody would ask out loud:
`execution_microstructure` on a D1 bar, `calendar_seasonality` at an intrabar horizon,
`session_handover` on a daily chart that has no sessions in it. So this organ enumerates ONLY the
ECONOMICALLY VALID cells -- the ontology's admissible (mechanism x asset_class x horizon x
session), the actor and information axes the mechanism DETERMINES, the charts that have bars, and
the regimes the desk has declared -- and reports the valid count beside the populated count, so
coverage is a ratio of real questions rather than of coordinates.

SEVEN AXES ARE CLOSED AND ONE IS OPEN. The regime axis is open: the desk names market states as it
finds them, and a certificate stamped `normal_day` must land in the grid rather than outside it, so
regimes observed in evidence join the mechanism's declared set. The other seven are closed
vocabularies; evidence landing outside them is COUNTED and sampled in `unmeasured`, never quietly
admitted -- a cell the ontology calls inadmissible that somebody tested anyway is a finding about
the desk, not a licence to widen the grid.

THE VALUE RANKS THE HOLES. value = the mechanism's MEASURED survivor rate (Laplace-smoothed, so an
untested mechanism reads the 0.5 prior rather than 0 or 1) x the asset class's independence bonus
(1/(1+live sleeves there), because the binding constraint is n_eff and a ninth sleeve in the class
that already holds forty buys almost nothing) x data readiness (READY 1.0, UNSEEN 0.45,
DATA_MISSING 0.15 -- acquisition is a real path, a slower one). Nothing here sizes, gates or
certifies: it ranks where the next trial should go.

    python desks/mt5/research/research_gap_map.py               # write the map
    python desks/mt5/research/research_gap_map.py --dry-run     # print it, write nothing
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from research import axis_registry as AX  # noqa: E402

REPORTS, DATA = DESK / "reports", DESK / "data"
UNIVERSE_DIR = DATA / "universe"
SLEEVES = DATA / "sleeves.json"
SHADOW = REPORTS / "shadow" / "shadow_state.json"
SURVIVORS = REPORTS / "UNIVERSAL_SURVIVORS.json"
GATE_LEDGER = DATA / "hypotheses" / "gate_verdict_ledger.jsonl"
GRAPH = DATA / "hypothesis_graph.jsonl"
RESEARCH_QUEUE = DATA / "research_queue.json"
OUT = REPORTS / "RESEARCH_GAP_MAP.json"

BUDGET_S = 240.0
MAX_LEDGER_LINES = 400_000
MAX_GRAPH_LINES = 80_000
MAX_POPULATED_PUBLISHED = 4000
TOP_HOLES = 60
#: How many regimes evidence may add to one mechanism. The regime axis is OPEN, not unbounded: a
#: parameter fingerprint read as a regime once put 1,569 "regimes" on 5,361 cells (axis_registry's
#: own measurement), which is an axis with one value per cell and therefore an axis measuring
#: nothing. The most frequent observed states join; the tail is counted in `unmeasured`.
MAX_OBSERVED_REGIMES = 6

STATES: tuple[str, ...] = ("UNSEEN", "DATA_MISSING", "READY", "TESTING", "FAILED", "SURVIVED",
                           "FORWARD", "LIVE")
STATE_RANK = {s: i for i, s in enumerate(STATES)}
#: Evidence states only -- the three below them are DERIVED from the ground, never observed.
EVIDENCE_STATES = ("TESTING", "FAILED", "SURVIVED", "FORWARD", "LIVE")
READINESS = {"READY": 1.0, "UNSEEN": 0.45, "DATA_MISSING": 0.15}

CHARTS: tuple[str, ...] = ("M5", "M15", "H1", "H4", "D1")
#: Which holding buckets a chart can actually express. A horizon shorter than one bar is not
#: measurable on that chart, and one longer than ~50 bars is a different chart's question asked
#: badly -- both are refused here rather than enumerated and then never tested.
CHART_HORIZONS: dict[str, tuple[str, ...]] = {
    "M5": ("intrabar", "sub_4h"), "M15": ("intrabar", "sub_4h"),
    "H1": ("sub_4h", "sub_1d"), "H4": ("sub_1d", "multi_day"), "D1": ("multi_day",),
}
SESSIONS: tuple[str, ...] = ("all", "asia", "london", "ny", "overlap")
#: The states the desk declares and can condition on today. `unconditional` is always admissible:
#: a mechanism that only pays in one regime is a narrower claim than one that always pays, and the
#: always-on cell is the one the narrower claim must beat.
REGIMES: tuple[str, ...] = ("unconditional", "high_volatility", "low_volatility", "trending",
                            "ranging", "risk_off")

#: observable -> the paths on this box that would hold it. Presence is MEASURED, never assumed:
#: the desk has a depth PROBE and no depth SERIES, and a broker CFD venue publishes no liquidation
#: tape at all, so two mechanisms are DATA_MISSING here and that is a fact about the box.
OBSERVABLES: dict[str, tuple[str, ...]] = {
    "bars": ("data/universe",),
    "tick_tape": ("data/tape/ticks",),
    "order_book_depth": ("data/tape/depth",),
    "cot_positioning": ("data/cot", "data/cot_disagg", "data/cot_tff"),
    "macro_calendar": ("data/macro_pointintime", "data/macro", "data/macro_state.json"),
    "swap_rates": ("data/carry_state.json",),
    "dated_flow_calendar": ("data/forced_flow_calendar.json",),
    "option_open_interest": ("data/options_state.json", "data/options_archive.parquet"),
    "liquidation_prints": ("data/liquidations",),
}


@dataclass(frozen=True)
class Contract:
    """What a mechanism may economically be asked about. Charts, sessions, horizons and regimes
    are the ADMISSIBILITY the enumeration prunes against; `needs` is the observable without which
    the question cannot be asked at all; `ontology` names the `mechanism_ontology` contract this
    bridges to, where one exists, so the two vocabularies stay joined rather than parallel."""

    charts: tuple[str, ...] = CHARTS
    sessions: tuple[str, ...] = SESSIONS
    horizons: tuple[str, ...] = ("intrabar", "sub_4h", "sub_1d", "multi_day")
    regimes: tuple[str, ...] = REGIMES
    needs: tuple[str, ...] = ("bars",)
    classes: tuple[str, ...] = ()          # empty = every class in the hypothesis lane
    ontology: str = ""


_INTRADAY = ("M5", "M15", "H1", "H4")
_FAST = ("M5", "M15", "H1")
_SLOW = ("H4", "D1")

#: THE ADMISSIBILITY TABLE, declared by hand and short of a guess. Every mechanism
#: `axis_registry.MECHANISM_ACTOR` names appears here; a mechanism absent from it would be
#: enumerated against the defaults, which is a wider claim than anybody made.
CONTRACT: dict[str, Contract] = {
    # A handover between sessions cannot be asked of a bar that contains every session. This is
    # the rule the test pins: a session mechanism has NO D1 cell.
    "session_handover": Contract(charts=_INTRADAY, sessions=("asia", "london", "ny", "overlap"),
                                 horizons=("intrabar", "sub_4h", "sub_1d")),
    "session_information_handoff": Contract(charts=_INTRADAY,
                                            sessions=("asia", "london", "ny", "overlap"),
                                            horizons=("intrabar", "sub_4h", "sub_1d")),
    "hedging_demand_close_flow": Contract(charts=_INTRADAY, sessions=("london", "ny", "overlap"),
                                          horizons=("intrabar", "sub_4h")),
    "fx_fixing_flow": Contract(charts=_FAST, sessions=("london", "ny", "overlap"),
                               horizons=("intrabar", "sub_4h"),
                               classes=("forex", "forex_exotics", "commodities")),
    "macro_release": Contract(charts=_INTRADAY, horizons=("intrabar", "sub_4h", "sub_1d"),
                              needs=("bars", "macro_calendar")),
    "forced_flow": Contract(charts=("H1", "H4", "D1"), horizons=("sub_1d", "multi_day"),
                            needs=("bars", "dated_flow_calendar")),
    "carry_rollover": Contract(charts=_SLOW, sessions=("all",),
                               horizons=("sub_1d", "multi_day"), needs=("bars", "swap_rates"),
                               classes=("forex", "forex_exotics", "bonds", "commodities"),
                               ontology="PERP_FUNDING_CARRY"),
    "positioning_crowding": Contract(charts=_SLOW, sessions=("all",), horizons=("multi_day",),
                                     needs=("bars", "cot_positioning"),
                                     classes=("forex", "commodities", "soft_commodity", "energy",
                                              "indices")),
    "calendar_seasonality": Contract(charts=_SLOW, sessions=("all",),
                                     horizons=("sub_1d", "multi_day")),
    "relative_value_dislocation": Contract(horizons=("sub_4h", "sub_1d", "multi_day"),
                                           ontology="CROSS_SECTIONAL_MOMENTUM"),
    "cross_market_lead": Contract(charts=_INTRADAY, horizons=("intrabar", "sub_4h", "sub_1d"),
                                  ontology="CROSS_VENUE_PRICE_DISCOVERY"),
    "trend_persistence": Contract(),
    "range_reversion": Contract(horizons=("intrabar", "sub_4h", "sub_1d")),
    "breakout_liquidity": Contract(horizons=("intrabar", "sub_4h", "sub_1d")),
    "volatility_shock": Contract(horizons=("intrabar", "sub_4h", "sub_1d")),
    "regime_transition": Contract(charts=("H1", "H4", "D1"), horizons=("sub_1d", "multi_day")),
    "execution_microstructure": Contract(charts=_FAST, horizons=("intrabar",),
                                         needs=("bars", "tick_tape"),
                                         ontology="ORDER_FLOW_IMBALANCE"),
    "gamma_hedging_state": Contract(charts=_FAST, horizons=("intrabar", "sub_4h"),
                                    needs=("bars", "option_open_interest"),
                                    classes=("indices", "commodities", "forex")),
    "inventory_shock": Contract(charts=_FAST, horizons=("intrabar",),
                                needs=("bars", "order_book_depth")),
    "forced_liquidation": Contract(charts=_FAST, horizons=("intrabar", "sub_4h"),
                                   needs=("bars", "liquidation_prints"),
                                   ontology="FORCED_LIQUIDATION"),
}

#: A mechanism the family table gives no information axis (it reached the desk through the
#: ontology rather than through a family) still needs one, or it would be enumerated at UNKNOWN
#: and its cells would never join a candidate's.
FALLBACK_INFORMATION: dict[str, tuple[str, ...]] = {
    "forced_liquidation": ("microstructure", "positioning"),
}

RULE = ("research moves toward the highest-value holes; a hole is named, never assumed covered")

#: The last build's index, so `holes()` and `state_of()` answer without re-reading the box.
_LAST: dict[str, Any] | None = None


# ------------------------------------------------------------------------------ tolerant reading
def _read(path: Path, note: dict[str, str]) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig", errors="replace"))
    except FileNotFoundError:
        note[str(path)] = "ABSENT"
    except (OSError, ValueError) as exc:
        note[str(path)] = f"UNREADABLE: {type(exc).__name__}"
    return None


def _read_jsonl(path: Path, note: dict[str, str], tail: int) -> list[dict[str, Any]]:
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]
    except FileNotFoundError:
        note[str(path)] = "ABSENT"
        return []
    except OSError as exc:
        note[str(path)] = f"UNREADABLE: {type(exc).__name__}"
        return []
    out: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _tok(value: Any) -> str:
    return AX._tok(value)


def key_of(axes: dict[str, str]) -> str:
    """The cell's identity, in `registry.GRID_AXES` order and the registry's own spelling, so a
    candidate's `grid_cell` column and a map cell are the SAME string."""
    return "|".join(str(axes.get(a) or "unknown").lower() for a in R.GRID_AXES)


def axes_of_key(cell: str) -> dict[str, str]:
    parts = str(cell).split("|")
    return {a: (parts[i] if i < len(parts) else "unknown") for i, a in enumerate(R.GRID_AXES)}


# ------------------------------------------------------------------------------ the ground
def bars_by_class(note: dict[str, str]) -> dict[str, dict[str, int]]:
    """{asset_class: {chart: n_symbols with bars}} over the HYPOTHESIS lane only.

    Single-name equities are traded on news and never hunted statistically (principal, 2026-09-06),
    so an equity bar file is not coverage of anything this map ranks. A symbol the broker registry
    does not classify is UNCLASSIFIED and counted in `unmeasured`, never bucketed."""
    out: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    try:
        from research.universe_policy import asset_class_of, may_hypothesise
    except ImportError:                                                          # pragma: no cover
        note["universe_policy"] = "UNIMPORTABLE: the lane router is absent"
        return {}
    n_files = n_unclassified = 0
    try:
        files = sorted(Path(UNIVERSE_DIR).glob("*.parquet"))
    except OSError:
        files = []
    if not files:
        note[str(UNIVERSE_DIR)] = "NO BAR FILES"
    for path in files:
        stem = path.stem
        if "_" not in stem:
            continue
        symbol, chart = stem.rsplit("_", 1)
        chart = AX.normalise_chart(chart)
        if chart not in CHARTS:
            continue
        n_files += 1
        if not may_hypothesise(symbol):
            continue
        klass = _tok(asset_class_of(symbol))
        if not klass:
            n_unclassified += 1
            continue
        out[klass][chart] += 1
    note["_bar_files"] = str(n_files)
    note["_unclassified_symbols"] = str(n_unclassified)
    return {k: dict(v) for k, v in out.items()}


def available_observables(note: dict[str, str]) -> dict[str, bool]:
    """Which declared observables this box actually holds. A directory counts only when it has
    something in it: an empty folder left by a retired collector reads as data and is not."""
    out: dict[str, bool] = {}
    for name, paths in OBSERVABLES.items():
        found = False
        for rel in paths:
            p = ROOT / rel if (ROOT / rel).exists() else DESK / rel
            try:
                if p.is_dir():
                    found = any(p.iterdir())
                elif p.exists():
                    found = p.stat().st_size > 0
            except OSError:
                found = False
            if found:
                break
        out[name] = found
        if not found:
            note[f"observable:{name}"] = "ABSENT on this box"
    return out


def information_of(mechanism: str) -> tuple[str, ...]:
    """The information axes a mechanism is actually implemented on, from the family table."""
    infos = sorted({i for (m, i, _s) in AX.FAMILY_TABLE.values() if m == mechanism})
    if not infos:
        infos = list(FALLBACK_INFORMATION.get(mechanism, ()))
    return tuple(infos)


# ------------------------------------------------------------------------------ the evidence
def _axes(symbol: Any, family: Any, params: Any, timeframe: Any = None, session: Any = None,
          regime_hint: Any = None) -> dict[str, str]:
    ten = AX.axis_cell(symbol, family, params if isinstance(params, dict) else {},
                       timeframe, session, None, regime_hint)
    return {"asset_class": ten["asset_class"], "mechanism": ten["mechanism"],
            "economic_actor": ten["economic_actor"], "information": ten["information_source"],
            "chart": ten["chart"], "session": ten["session"], "horizon": ten["horizon"],
            "regime": ten["regime"]}


def collect_evidence(note: dict[str, str]) -> tuple[dict[str, str], dict[str, int]]:
    """{cell -> strongest evidence state} over sleeves, forward clocks, certificates, the gate
    ledger, the registry's queue and the docket. The STRONGEST claim wins, as `axis_registry`
    resolves the same disagreement -- six sources describe overlapping cells by construction."""
    ev: dict[str, str] = {}
    counts: Counter[str] = Counter()

    def add(axes: dict[str, str], state: str, source: str) -> None:
        cell = key_of(axes)
        counts[source] += 1
        old = ev.get(cell)
        if old is None or STATE_RANK[state] > STATE_RANK[old]:
            ev[cell] = state

    doc = _read(SLEEVES, note)
    rows = (doc.get("sleeves") if isinstance(doc, dict) else doc) or []
    for s in (rows.values() if isinstance(rows, dict) else rows):
        if not isinstance(s, dict) or not s.get("symbol"):
            continue
        if str(s.get("status") or "").upper() not in ("LIVE", "STANDBY"):
            continue
        add(_axes(s.get("symbol"), s.get("family"), s, s.get("timeframe"), s.get("session")),
            "LIVE", "sleeves")

    doc = _read(SHADOW, note)
    for key, row in (doc or {}).items() if isinstance(doc, dict) else []:
        if not isinstance(row, dict):
            continue
        p = AX.parse_shadow_key(str(key))
        if not p["symbol"]:
            continue
        add(_axes(p["symbol"], p["family"], row, row.get("timeframe"), p["session"], p["regime"]),
            "FORWARD", "forward_clocks")

    doc = _read(SURVIVORS, note)
    surv = (doc.get("survivors") if isinstance(doc, dict) else doc) or {}
    for row in (surv.values() if isinstance(surv, dict) else surv):
        if not isinstance(row, dict):
            continue
        spec = row.get("shadow_spec") if isinstance(row.get("shadow_spec"), dict) else {}
        cellname = str(row.get("cell") or "")
        bits = cellname.split()
        family = spec.get("family") or (bits[1] if len(bits) > 1 else "")
        # `AUDNZD dav_range_filter_adx SHORT afternoon NORMAL_DAY`: a session token if one of the
        # trailing words is a session, and the regime is the LAST word that is neither a session
        # nor a side -- the shape the certificate writer has used since hunt16.
        tail = [b for b in bits[2:] if b.upper() not in ("LONG", "SHORT", "BOTH")]
        session = next((b for b in tail if _tok(b) in AX.SESSION_ALIAS), None)
        regime = next((b for b in reversed(tail) if _tok(b) not in AX.SESSION_ALIAS), None)
        add(_axes(row.get("sym") or (bits[0] if bits else ""), family, spec.get("params"),
                  spec.get("chart"), session, regime), "SURVIVED", "certificates")

    for row in _read_jsonl(GATE_LEDGER, note, MAX_LEDGER_LINES):
        passed = row.get("passed")
        p = AX.parse_shadow_key(str(row.get("cell") or ""))
        sym = row.get("sym") or p["symbol"]
        if not sym:
            continue
        axes = _axes(sym, row.get("family") or p["family"], None, None, p["session"], p["regime"])
        # A judged PASS is not a certificate -- `UNIVERSAL_SURVIVORS` mints those, and the
        # precedence above lets it win wherever it has. A judged pass here is activity: TESTING.
        add(axes, "FAILED" if passed is False else "TESTING", "gate_ledger")

    try:
        for status in ("queued", "claimed", "donated"):
            for row in R.candidates(status=status, limit=20000):
                cell = str(row.get("grid_cell") or "")
                if cell and cell.count("|") == len(R.GRID_AXES) - 1:
                    # The registry's own `grid_cell` column is already this key, written by
                    # `registry.grid_cell` over the same GRID_AXES -- so it is used verbatim
                    # rather than re-derived, and the two can never disagree. TESTING is the
                    # weakest evidence state, so `setdefault` never demotes a stronger claim.
                    counts["registry_candidates"] += 1
                    ev.setdefault(cell, "TESTING")
                    continue
                add(_axes(row.get("symbol"), row.get("family"), None, row.get("chart"),
                          row.get("session"), row.get("regime")), "TESTING",
                    "registry_candidates")
    except Exception as exc:
        note["registry"] = f"UNREADABLE: {type(exc).__name__}: {str(exc)[:80]}"

    doc = _read(RESEARCH_QUEUE, note)
    for row in doc if isinstance(doc, list) else []:
        if isinstance(row, dict) and row.get("family"):
            add(_axes(row.get("symbol") or row.get("sym"), row.get("family"), row.get("params"),
                      row.get("timeframe"), row.get("session")), "TESTING", "research_queue")

    for row in _read_jsonl(GRAPH, note, MAX_GRAPH_LINES):
        if row.get("symbol") and row.get("family"):
            add(_axes(row.get("symbol"), row.get("family"), row.get("params"),
                      (row.get("params") or {}).get("timeframe")
                      if isinstance(row.get("params"), dict) else None,
                      None), "TESTING", "hypothesis_graph")

    return ev, dict(counts)


def live_by_class(note: dict[str, str]) -> dict[str, int]:
    """Live sleeves per asset class -- the independence denominator. The book's concentration is
    the binding constraint (n_eff 5.6 across 65 sleeves, measured 2026-09-14), so a hole in a
    class already carrying forty sleeves is worth a fraction of the same hole in an empty one."""
    doc = _read(SLEEVES, note)
    rows = (doc.get("sleeves") if isinstance(doc, dict) else doc) or []
    out: Counter[str] = Counter()
    for s in (rows.values() if isinstance(rows, dict) else rows):
        if isinstance(s, dict) and str(s.get("status") or "").upper() == "LIVE":
            out[AX.asset_class_of(str(s.get("symbol") or ""))] += 1
    return dict(out)


# ------------------------------------------------------------------------------ the enumeration
def _regimes_for(mechanism: str, observed: dict[str, Counter[str]]) -> tuple[str, ...]:
    declared = list(CONTRACT.get(mechanism, Contract()).regimes)
    extra = [r for r, _ in observed.get(mechanism, Counter()).most_common()
             if r not in declared][:MAX_OBSERVED_REGIMES]
    return tuple(declared + extra)


def enumerate_cells(ground: dict[str, Any], budget_s: float) -> tuple[dict[str, dict[str, str]],
                                                                     dict[str, Any]]:
    """Every economically valid cell, as {cell -> axes}. Stops on the budget and SAYS SO."""
    bars: dict[str, dict[str, int]] = ground["bars_by_class"]
    classes = sorted(bars)
    charts = [c for c in CHARTS if any(c in v for v in bars.values())]
    observed = ground["observed_regimes"]
    t0 = time.monotonic()
    cells: dict[str, dict[str, str]] = {}
    truncated = False
    for mech, contract in sorted(CONTRACT.items()):
        actor = AX.MECHANISM_ACTOR.get(mech, AX.UNKNOWN).lower()
        infos = information_of(mech)
        if not infos:
            continue
        mech_classes = [c for c in classes if not contract.classes or c in contract.classes]
        regimes = _regimes_for(mech, observed)
        for info in infos:
            for klass in mech_classes:
                for chart in charts:
                    if chart not in contract.charts:
                        continue
                    horizons = [h for h in contract.horizons if h in CHART_HORIZONS[chart]]
                    for session in contract.sessions:
                        for horizon in horizons:
                            for regime in regimes:
                                axes = {"asset_class": klass, "mechanism": mech,
                                        "economic_actor": actor, "information": info,
                                        "chart": chart, "session": session,
                                        "horizon": horizon, "regime": regime}
                                cells[key_of(axes)] = axes
        if time.monotonic() - t0 > budget_s:
            truncated = True
            break
    return cells, {"truncated": truncated, "seconds": round(time.monotonic() - t0, 2),
                   "classes": classes, "charts": charts}


def _derived_state(axes: dict[str, str], ground: dict[str, Any]) -> str:
    """READY, DATA_MISSING or UNSEEN for a cell no evidence touches."""
    needs = CONTRACT.get(axes["mechanism"], Contract()).needs
    have = ground["observables"]
    if any(not have.get(n, False) for n in needs if n != "bars"):
        return "DATA_MISSING"
    if ground["bars_by_class"].get(axes["asset_class"], {}).get(axes["chart"], 0) > 0:
        return "READY"
    return "UNSEEN"


def survivor_rates(evidence: dict[str, str]) -> dict[str, float]:
    """Per mechanism: (survivors + 1) / (judged + 2). Laplace, so a mechanism nobody has judged
    reads the registry's own 0.5 PRIOR -- an unmeasured mechanism must not outrank a measured one
    by absence, and must not be buried by it either."""
    won: Counter[str] = Counter()
    judged: Counter[str] = Counter()
    for cell, state in evidence.items():
        mech = axes_of_key(cell)["mechanism"]
        if state in ("SURVIVED", "FORWARD", "LIVE"):
            won[mech] += 1
            judged[mech] += 1
        elif state == "FAILED":
            judged[mech] += 1
    mechs = set(CONTRACT) | set(won) | set(judged)
    return {m: float((won[m] + 1.0) / (judged[m] + 2.0)) for m in mechs}


def outside_reasons(outside: dict[str, str], cells: dict[str, dict[str, str]]) -> dict[str, int]:
    """WHY a tested cell is not in the grid, per axis. A count alone is not actionable: `mechanism
    is not in the vocabulary` (the docket's `discovered` family names no mechanism) and `the
    combination is inadmissible` (a carry cell judged on an H1 asia bar) are different findings
    and need different fixes."""
    vocab: dict[str, set[str]] = {a: set() for a in R.GRID_AXES}
    for axes in cells.values():
        for axis, value in axes.items():
            vocab[axis].add(value)
    out: Counter[str] = Counter()
    for cell in outside:
        axes = axes_of_key(cell)
        bad = [a for a in R.GRID_AXES if axes[a] not in vocab[a]]
        if bad:
            for a in bad:
                out[f"{a}={axes[a]} is outside the vocabulary"] += 1
        else:
            out["every axis value is known; the COMBINATION is inadmissible"] += 1
    return dict(out.most_common(24))


def _debt_cells(cells: dict[str, dict[str, str]], states: dict[str, str]) -> int:
    """READY or UNSEEN cells with a TESTED NEIGHBOUR -- a populated cell one axis away.

    This is the research debt the ledger means: not "everything untested" (which is most of any
    honest grid) but the extension nobody would argue against. The desk tested EURUSD trend on H1
    in london; the same mechanism on H4 in london is one axis away, and nothing but the search's
    own habit explains why it was never asked."""
    masked: list[set[str]] = []
    for i in range(len(R.GRID_AXES)):
        seen: set[str] = set()
        for cell, state in states.items():
            if state in EVIDENCE_STATES:
                parts = cell.split("|")
                parts[i] = "*"
                seen.add("|".join(parts))
        masked.append(seen)
    n = 0
    for cell in cells:
        if states.get(cell) not in ("READY", "UNSEEN"):
            continue
        parts = cell.split("|")
        for i in range(len(R.GRID_AXES)):
            probe = list(parts)
            probe[i] = "*"
            if "|".join(probe) in masked[i]:
                n += 1
                break
    return n


# ------------------------------------------------------------------------------ the build
def build(budget_s: float = BUDGET_S) -> dict[str, Any]:
    """The map. Every number here is read off this box; every absence is named."""
    global _LAST
    t0 = time.monotonic()
    note: dict[str, str] = {}
    evidence, source_counts = collect_evidence(note)
    observed: dict[str, Counter[str]] = defaultdict(Counter)
    for cell in evidence:
        a = axes_of_key(cell)
        observed[a["mechanism"]][a["regime"]] += 1
    ground = {"bars_by_class": bars_by_class(note), "observables": available_observables(note),
              "observed_regimes": observed, "live_by_class": live_by_class(note)}
    cells, enum_note = enumerate_cells(ground, budget_s)

    states: dict[str, str] = {}
    for cell, axes in cells.items():
        states[cell] = evidence.get(cell) or _derived_state(axes, ground)
    outside = {c: s for c, s in evidence.items() if c not in cells}

    rates = survivor_rates(evidence)
    live = ground["live_by_class"]
    holes_rows: list[dict[str, Any]] = []
    for cell, axes in cells.items():
        state = states[cell]
        if state not in ("READY", "UNSEEN", "DATA_MISSING"):
            continue
        rate = rates.get(axes["mechanism"], R.PRIOR)
        n_live = int(live.get(axes["asset_class"], 0))
        indep = 1.0 / (1.0 + float(n_live))
        ready = READINESS[state]
        holes_rows.append({"cell": cell, "state": state,
                           "value": round(float(rate * indep * ready), 6),
                           "why": (f"{axes['mechanism']} survives {rate:.2f} of what it is judged "
                                   f"on; {axes['asset_class']} carries {n_live} live sleeve(s); "
                                   f"readiness {ready:.2f} ({state})")})
    if holes_rows:
        order = np.argsort(-np.asarray([h["value"] for h in holes_rows], dtype=float),
                           kind="stable")
        holes_rows = [holes_rows[int(i)] for i in order]

    by_state = dict.fromkeys(STATES, 0)
    for s in states.values():
        by_state[s] += 1
    coverage: dict[str, dict[str, int]] = {a: {} for a in R.GRID_AXES}
    for cell, state in states.items():
        if state not in EVIDENCE_STATES:
            continue
        for axis, value in axes_of_key(cell).items():
            coverage[axis][value] = coverage[axis].get(value, 0) + 1

    populated = {c: s for c, s in states.items() if s in EVIDENCE_STATES}
    doc = {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "n_valid_cells": len(cells),
        "n_populated": len(populated),
        "populated_share": (round(len(populated) / len(cells), 6) if cells else None),
        "by_state": by_state,
        "top_holes": holes_rows[:TOP_HOLES],
        "coverage_by_axis": {a: dict(sorted(v.items(), key=lambda kv: -kv[1])[:60])
                             for a, v in coverage.items()},
        "research_debt_cells": _debt_cells(cells, states),
        "survivor_rate_by_mechanism": {m: round(v, 4) for m, v in sorted(rates.items())},
        "ground": {"asset_classes": enum_note["classes"], "charts_with_bars": enum_note["charts"],
                   "bars_by_class": ground["bars_by_class"],
                   "observables": ground["observables"],
                   "live_sleeves_by_class": live},
        "populated_cells": dict(list(populated.items())[:MAX_POPULATED_PUBLISHED]),
        "unmeasured": {
            "inputs": note,
            "evidence_rows_by_source": source_counts,
            "evidence_outside_the_grid": len(outside),
            "evidence_outside_why": outside_reasons(outside, cells),
            "evidence_outside_sample": sorted(outside)[:20],
            "mechanisms_without_a_judged_cell": sorted(
                m for m in CONTRACT if m not in {axes_of_key(c)["mechanism"] for c in evidence}),
            "mechanisms_data_missing": sorted(
                m for m, c in CONTRACT.items()
                if any(not ground["observables"].get(n, False) for n in c.needs if n != "bars")),
            "budget_exhausted": bool(enum_note["truncated"]),
            "enumeration_seconds": enum_note["seconds"],
            "populated_cells_published": min(len(populated), MAX_POPULATED_PUBLISHED),
            "why": ("an absent input is a named UNMEASURED, never a zero: a zero says the organ "
                    "ran and found nothing, which is the one lie this map cannot afford"),
        },
        "seconds": round(time.monotonic() - t0, 2),
        "rule": RULE,
    }
    _LAST = {"states": states, "cells": cells, "holes": holes_rows, "ground": ground,
             "evidence": evidence}
    return doc


def holes(k: int = 25) -> list[dict[str, Any]]:
    """The k highest-value holes. Builds the map when nothing is cached in this process."""
    if _LAST is None:
        build()
    return list((_LAST or {}).get("holes", []))[:max(0, int(k))]


def state_of(cell: str | dict[str, str]) -> str:
    """The ONE state of a cell. `INVALID` when the coordinate is not an economically valid cell --
    which is a verdict about the question, not about the desk's coverage of it."""
    if _LAST is None:
        build()
    idx = _LAST or {}
    key = key_of(cell) if isinstance(cell, dict) else str(cell)
    states: dict[str, str] = idx.get("states", {})
    if key in states:
        return states[key]
    if key in idx.get("evidence", {}):
        return str(idx["evidence"][key])
    return "INVALID"


def write(doc: dict[str, Any], path: Path | None = None) -> Path:
    p = Path(path or OUT)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)
    return p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--top", type=int, default=12)
    a = ap.parse_args(argv)
    doc = build(a.budget_s)
    print(f"research gap map: {doc['n_valid_cells']} economically valid cell(s), "
          f"{doc['n_populated']} populated, debt {doc['research_debt_cells']}")
    print("  " + "  ".join(f"{s}:{doc['by_state'][s]}" for s in STATES))
    for h in doc["top_holes"][:max(0, a.top)]:
        print(f"  {h['value']:.4f}  {h['state']:<12} {h['cell']}")
    if doc["unmeasured"]["budget_exhausted"]:
        print("  BUDGET EXHAUSTED: the enumeration is partial and the counts say so")
    if a.dry_run:
        print("  --dry-run: nothing written")
        return 0
    print(f"-> {write(doc)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
