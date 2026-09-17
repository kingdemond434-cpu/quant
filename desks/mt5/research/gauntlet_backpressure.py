"""M23 -- THE GAUNTLET TALKS BACK: mining and judging are one loop, not a one-way pipeline.

THE PRINCIPAL, 2026-09-17: mining <-> gauntlet. Today the arrow points one way. The miners
generate, the gauntlet judges, and the only thing that flows back upstream is a verdict on one
cell -- so the desk re-learns the same refusal ten thousand times. Measured on this tree the day
this organ was written: 3,364 verdicts in the ledger, 1,670 of them terminal at `in_sample_screen`
and 714 at `deflated_sharpe`, on a docket the axis registry had already shown to be one region
sampled tens of thousands of times. None of that record ever reached the thing that generates.

WHAT FLOWS BACK, AND IT IS THREE THINGS:

    MESSAGES.  Seven named conditions, each with its measured trigger and a concrete instruction.
               A message is a MEASUREMENT plus an INSTRUCTION; one with no reading attached is an
               opinion and is not published.
    PRIORS.    Every failure class moves a number. For each (family, chart, asset_class) bucket
               judged at least MIN_BUCKET_JUDGED times, the Jeffreys-smoothed pass rate becomes
               `p_edge_prior` in the canonical registry's research memory, keyed so a re-run
               refreshes the row rather than duplicating it.
    THE FLOOR. Cold exploration keeps its share. A machine that only generates where it has
               already succeeded is a fixed point of its own history, so the report states the
               share of born cells landing in grid cells that have never produced a pass and flags
               it under `negative_knowledge.EXPLORE_FLOOR`. The floor is not fairness: it is what
               lets every prior above be wrong in a recoverable way.

WHAT THIS ORGAN NEVER DOES: delete a cell, lower a bar, cap a book or shrink a budget. Every
message says generate DIFFERENTLY, never generate LESS (GROWTH_GOVERNANCE Rule 1). `backlog_
growing` is the one message about volume and its instruction is an ORDER of service, not a cut.

THE PRIOR CONTRACT, for the discovery compiler and the moat engines:
`registry.memories(category="candidate_prior")`, keyed `prior:<family>|<chart>|<asset_class>`,
metrics as `build()["prior_contract"]` lists them. `p_edge_prior` is (passed + 0.5) /
(judged + 1) -- the Jeffreys posterior mean, which is what `enqueue_candidate(p_edge=...)`
multiplies into the candidate score. A bucket under the floor is NOT written: a rate on nineteen
cells is arithmetic, and the registry's PRIOR (0.5) is the honest reading for one the desk has
barely judged.

THE BANDIT is read, never written. `bandit.evidence(graph_rows, ...)` IS its documented evidence
path and it accepts the rows this organ already holds, so it is CALLED -- read-only. What it
cannot do is RECEIVE an external evidence row, so the intended feedback is published under
`bandit.intended_feedback` and named unwired there, with its owner (III.16).

    python desks/mt5/research/gauntlet_backpressure.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

GATE_LEDGER = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
GRAPH = DESK / "data" / "hypothesis_graph.jsonl"
GAUNTLET_REPORT = DESK / "reports" / "universal_gates_external.json"
GAUNTLET_SOURCE = DESK / "scripts" / "external_gauntlet.py"
NOVELTY = DESK / "reports" / "NOVELTY_GATE.json"
OUT = DESK / "reports" / "GAUNTLET_BACKPRESSURE.json"

#: Bounds, published rather than assumed: the box holding the live terminal has 8 GB and a dozen
#: resident python processes, and a reporting organ that becomes an hour of IO is a defect.
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_LINES = 500_000
#: Two trailing windows. Messages are measured on the FIRST; the second is published beside it so
#: a session can tell a spike from a standing state.
WINDOWS: tuple[tuple[str, float], ...] = (("24h", 24.0), ("7d", 168.0))

#: WHICH TERMINAL GATE MEANS WHICH FAILURE CLASS (registry.FAILURE_CLASSES). DECLARED, because a
#: gate name is machinery and a failure class is an economic statement, and no join between them
#: exists anywhere in this repo. Read it as: what did the desk LEARN when this gate refused?
#: symbol_eligibility (the instrument cannot carry the rule) is WRONG_ASSET. economic_prior (no
#: named payer), in_sample_screen (Sharpe <= 0), expected_value (mean <= 0 on that same net
#: series), deflated_sharpe (does not survive its own multiplicity), reality_check_spa (no better
#: than the best of the null family) and lockbox (absent on a sealed sample the search never
#: touched) all say NO_EDGE. pbo and cpcv say the number does not hold out of sample (UNSTABLE);
#: walk_forward says it held in some windows and not forward through time (REGIME_SPECIFIC);
#: stress_costs and swap_cost are the unambiguous COST deaths.
#:
#: `observations` is UNMAPPED ON PURPOSE -- too few observations is work not done, never a
#: refutation (L1.28a) -- and is counted under `unmeasured_gates`. `expected_value` could be
#: argued the other way, since a positive gross and a negative net edge HAS been killed by costs;
#: the gate cannot separate the two and in_sample_screen is the same test on the same array, so
#: splitting them would make the cost mix a statement about which of two identical tests fired
#: first.
GATE_FAILURE_CLASS: dict[str, str | None] = {
    "symbol_eligibility": "wrong_asset", "economic_prior": "no_edge", "observations": None,
    "in_sample_screen": "no_edge", "deflated_sharpe": "no_edge", "pbo": "unstable",
    "reality_check_spa": "no_edge", "cpcv": "unstable", "walk_forward": "regime_specific",
    "stress_costs": "cost_killed", "swap_cost": "cost_killed", "lockbox": "no_edge",
    "expected_value": "no_edge", "UNKNOWN": None, "PASSED": None, "": None,
}
#: Asset-class tokens that ARE FX in `universe_policy.HYPOTHESIS_CLASSES`' vocabulary, after
#: `axis_registry`'s tokeniser. Matching the literal "fx" alone would read 0% on a docket that is
#: entirely `forex_majors`.
FX_CLASSES = frozenset({"fx", "forex", "fx_major", "fx_cross", "fx_exotic",
                        "forex_majors", "forex_crosses", "forex_exotics"})
#: Mechanisms that are an EVENT or a FORCED FLOW: somebody must trade on a dated calendar, which
#: is the one kind of edge that does not need the counterparty to be wrong.
EVENT_MECHANISMS = frozenset({"macro_release", "forced_flow", "fx_fixing_flow",
                              "hedging_demand_close_flow", "calendar_seasonality"})
#: Where an intake row may carry its point-in-time stamp. A row carrying none of them is not
#: PIT-compliant; the share is a measurement and zero is a real answer.
PIT_KEYS: tuple[str, ...] = ("available_time", "knowable_at", "as_of", "pit_time", "pit_status",
                             "available_at")

MIN_BUCKET_JUDGED = 20
DUP_SHARE_TRIGGER = 0.20
COST_KILLED_TRIGGER = 0.50
CONCENTRATION_TRIGGER = 0.40
EVENT_SHARE_TRIGGER = 0.10
PIT_TRIGGER = 0.90
CROSS_ASSET_TRIGGER = 0.15
BACKLOG_CAPACITY_MULTIPLE = 2.0
TOP_GRID_CELLS = 3
UNKNOWN = "UNKNOWN"

try:  # an organ that cannot run without an import is an organ that does not run (III.16)
    from libs.moat import registry as _registry
except Exception:  # pragma: no cover - only on a tree without libs/
    _registry = None  # type: ignore[assignment]


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _at(value: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _read_json(path: Path, note: dict[str, str]) -> Any:
    """Parse `path`, or record exactly why it produced nothing. Never raises."""
    try:
        size = path.stat().st_size
    except OSError:
        note[path.name] = "ABSENT"
        return None
    if size > MAX_INPUT_BYTES:
        note[path.name] = f"TOO_LARGE({size})"
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        note[path.name] = f"UNREADABLE({type(exc).__name__})"
        return None
    note[path.name] = "READ"
    return doc


def _read_jsonl(path: Path, note: dict[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8-sig", errors="replace") as fh:
            for i, raw in enumerate(fh):
                if i >= MAX_LINES:
                    note[path.name] = f"TRUNCATED({MAX_LINES})"
                    return rows
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        note[path.name] = "ABSENT"
        return rows
    note[path.name] = "READ"
    return rows


def _rel(path: Path) -> str:
    """`path` inside the repo, or its plain string: a tmp path has no relative form, and an organ
    that raises while describing its own output is an organ nobody can test."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _share(num: float, den: float) -> float | None:
    return None if den <= 0 else round(float(num) / float(den), 4)


def axes_of(symbol: Any, family: Any, params: Any = None) -> dict[str, str]:
    """The ten axes of a cell, or UNKNOWNs when the axis registry cannot be reached."""
    try:
        import axis_registry as ar
        return ar.axis_cell(symbol, family, params if isinstance(params, dict) else None)
    except Exception:
        return {"asset_class": UNKNOWN, "chart": UNKNOWN, "session": UNKNOWN,
                "mechanism": UNKNOWN, "information_source": UNKNOWN}


def gate_class(gate: Any) -> str | None:
    """The declared failure class of a terminal gate; None when the gate maps to none."""
    return GATE_FAILURE_CLASS.get(str(gate or ""))


def born_cells(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per hypothesis id, stamped with its EARLIEST `at` -- the cell's birth.

    The graph is append-on-change, so an id appears when it is born and again when its fate moves.
    Counting rows would count a cell's death as an intake.
    """
    first: dict[str, dict[str, Any]] = {}
    for r in rows:
        rid = str(r.get("id") or "")
        if not rid:
            continue
        t = _at(r.get("at") or r.get("born_at"))
        prev = first.get(rid)
        if prev is None or (t is not None and (prev["_t"] is None or t < prev["_t"])):
            first[rid] = {**r, "_t": t}
    return list(first.values())


def verdicts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Verdict rows with a parsed timestamp; every row is an event, cells may repeat."""
    return [{**r, "_t": _at(r.get("at"))} for r in rows]


def _declared_constant(text: str, name: str) -> float | None:
    m = re.search(rf"^{re.escape(name)}\s*[:=].*?([0-9]+(?:\.[0-9]+)?)", text, re.M)
    return float(m.group(1)) if m else None


def capacity(note: dict[str, str], now: datetime | None = None) -> dict[str, Any]:
    """The gauntlet's per-pass capacity: what it DECLARES and what it last MEASURED.

    The declared constants are read out of `external_gauntlet.py` as TEXT rather than imported:
    that module pulls in the engine, the universe registry and five validation libraries, and a
    reporting organ that cannot run without them is an organ that does not run.
    """
    out: dict[str, Any] = {"declared": {}, "measured": {}}
    try:
        src = GAUNTLET_SOURCE.read_text(encoding="utf-8", errors="replace")
    except OSError:
        note[GAUNTLET_SOURCE.name] = "ABSENT"
        src = ""
    if src:
        note[GAUNTLET_SOURCE.name] = "READ"
        out["declared"] = {
            "fresh_build_budget_sec": _declared_constant(src, "FRESH_BUILD_BUDGET_SEC"),
            "declared_need_mb": _declared_constant(src, "DECLARED_NEED_MB"),
            "per_worker_mb": _declared_constant(src, "PER_WORKER_MB"),
            "why": "seconds of FIRST-TIME cell building one sweep may spend; cached cells are "
                   "free and are always all loaded"}
    doc = _read_json(GAUNTLET_REPORT, note)
    if not isinstance(doc, dict):
        out["measured"] = {"status": "UNMEASURED",
                           "why": f"{GAUNTLET_REPORT.name} {note.get(GAUNTLET_REPORT.name)}"}
        return out
    swept, at = _at(doc.get("swept_at")), (now or _now())
    out["measured"] = {
        "swept_at": doc.get("swept_at"),
        "age_h": None if swept is None else round((at - swept).total_seconds() / 3600.0, 2),
        **{k: doc.get(k) for k in ("n_cells", "n_judged", "n_unmeasured", "n_cells_discovered",
                                   "n_cells_deferred_build_budget",
                                   "n_cells_deferred_memory_budget", "memory_budget_mb",
                                   "workers")},
        "why": "cells judged by the LAST sweep: the per-pass capacity the desk actually has"}
    return out


def duplicate_share(born: list[dict[str, Any]], note: dict[str, str]) -> dict[str, Any]:
    """How much of the intake is the same rule twice, by three independent readings.

    Precedence for the TRIGGER: the registry's `search_count` first (it is the canonical dedupe
    and counts a re-enqueue the window never saw), the window's content hashes second. The
    novelty gate is reported beside them and never triggers -- it measures NEAR twins at a
    similarity threshold, which is a different question from an exact repeat.
    """
    hashes: Counter[str] = Counter()
    for r in born:
        a = axes_of(r.get("symbol"), r.get("family"), r.get("params"))
        hashes[json.dumps([str(r.get("family") or ""), str(r.get("symbol") or ""),
                           r.get("params") if isinstance(r.get("params"), dict) else {},
                           a.get("chart"), a.get("session")], sort_keys=True, default=str)] += 1
    repeats = sum(n - 1 for n in hashes.values() if n > 1)
    out: dict[str, Any] = {
        "n_born": len(born),
        "content_hash": {"distinct": len(hashes), "repeated_rows": repeats,
                         "share": _share(repeats, len(born)),
                         "why": "rows sharing (family, symbol, params, chart, session)"}}
    reg: dict[str, Any] = {"status": "UNMEASURED", "why": "libs.moat.registry unavailable"}
    if _registry is not None:
        try:
            rows = _registry.candidates(limit=100000)
            dup = sum(1 for r in rows if int(r.get("search_count") or 1) > 1)
            reg = ({"status": "MEASURED", "n_candidates": len(rows), "n_search_count_gt_1": dup,
                    "share": _share(dup, len(rows))} if rows else
                   {"status": "UNMEASURED", "n_candidates": 0,
                    "why": "research_candidates is empty: nothing has run "
                           "registry.sync_from_desk() on this box, so the canonical dedupe has no "
                           "rows to count. The content-hash reading is the fallback."})
        except Exception as exc:
            reg = {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
    out["registry"] = reg
    nov = _read_json(NOVELTY, note)
    if isinstance(nov, dict) and nov.get("n_screened"):
        out["novelty_gate"] = {
            "status": "MEASURED", "n_screened": nov.get("n_screened"),
            "n_redundant": nov.get("n_redundant"), "threshold": nov.get("threshold"),
            "redundant_share": _share(float(nov.get("n_redundant") or 0),
                                      float(nov.get("n_screened") or 0)),
            "why": "REDUNDANT means every measurable dimension reads as a named twin"}
    else:
        out["novelty_gate"] = {"status": "UNMEASURED",
                               "why": f"{NOVELTY.name} {note.get(NOVELTY.name, 'ABSENT')}"}
    if reg.get("status") == "MEASURED" and reg.get("share") is not None:
        out["share"], out["basis"] = reg["share"], "registry.search_count"
    else:
        out["share"], out["basis"] = out["content_hash"]["share"], "window content hashes"
    return out


def window_measure(born: list[dict[str, Any]], vers: list[dict[str, Any]], now: datetime,
                   hours: float, note: dict[str, str]) -> dict[str, Any]:
    """Every intake / testing / mix / concentration measure over one trailing window."""
    since = now - timedelta(hours=hours)
    prev = since - timedelta(hours=hours)
    b = [r for r in born if r.get("_t") is not None and r["_t"] >= since]
    b_prev = [r for r in born if r.get("_t") is not None and prev <= r["_t"] < since]
    v = [r for r in vers if r.get("_t") is not None and r["_t"] >= since]
    v_prev = [r for r in vers if r.get("_t") is not None and prev <= r["_t"] < since]
    judged = {str(r.get("cell") or "") for r in v if r.get("passed") is not None}
    judged_prev = {str(r.get("cell") or "") for r in v_prev if r.get("passed") is not None}
    n_pass = sum(1 for r in v if r.get("passed") is True)
    fails = [r for r in v if r.get("passed") is False]

    by_gate = Counter(str(r.get("terminal_gate") or UNKNOWN) for r in fails)
    by_class: Counter[str] = Counter()
    unmapped: Counter[str] = Counter()
    for gate, n in by_gate.items():
        cls = gate_class(gate)
        (by_class if cls else unmapped)[cls or gate] += n
    n_classified = sum(by_class.values())

    axes = [axes_of(r.get("symbol"), r.get("family"), r.get("params")) for r in b]
    grid = Counter(f"{a.get('asset_class')}|{a.get('chart')}|{a.get('session')}" for a in axes)
    top_grid = grid.most_common(TOP_GRID_CELLS)
    fx = sum(1 for a in axes if str(a.get("asset_class")) in FX_CLASSES
             and str(a.get("chart")) == "H1" and str(a.get("session")) == "asia")
    classes = Counter(str(a.get("asset_class")) for a in axes)
    top3 = [c for c, _ in classes.most_common(3)]
    outside = sum(n for c, n in classes.items() if c not in top3)
    event = sum(1 for a in axes if str(a.get("mechanism")) in EVENT_MECHANISMS
                or str(a.get("information_source")) == "event")
    pit = sum(1 for r in b if any(r.get(k) not in (None, "") for k in PIT_KEYS))
    backlog, backlog_prev = len(b) - len(judged), len(b_prev) - len(judged_prev)
    return {
        "hours": hours, "since": since.isoformat(timespec="seconds"),
        "intake": {"born_cells": len(b), "per_hour": round(len(b) / hours, 3),
                   "prior_window_born": len(b_prev)},
        "testing": {"verdicts": len(v), "cells_judged": len(judged),
                    "per_hour": round(len(judged) / hours, 3), "passed": n_pass,
                    "pass_rate": _share(n_pass, len(v))},
        "backlog": {"born_minus_judged": backlog, "prior_window": backlog_prev,
                    "growing": bool(backlog > backlog_prev), "capacity_cells": len(judged),
                    "over_capacity_multiple": (None if not judged
                                               else round(backlog / len(judged), 3))},
        "failure_mix": {"n_failures": len(fails), "by_gate": dict(by_gate.most_common()),
                        "by_class": dict(by_class.most_common()),
                        "class_shares": {k: _share(n, n_classified)
                                         for k, n in by_class.most_common()},
                        "unmeasured_gates": dict(unmapped.most_common()),
                        "cost_killed_share": _share(by_class.get("cost_killed", 0), n_classified)},
        "concentration": {"fx_h1_asia": fx, "fx_h1_asia_share": _share(fx, len(b)),
                          "top_grid_cells": [{"cell": c, "n": n, "share": _share(n, len(b))}
                                             for c, n in top_grid],
                          "top3_grid_share": _share(sum(n for _, n in top_grid), len(b)),
                          "distinct_grid_cells": len(grid)},
        "cross_asset_novelty": {"top3_asset_classes": top3, "outside_top3": outside,
                                "share": _share(outside, len(b)),
                                "by_asset_class": dict(classes.most_common(8))},
        "event_mechanisms": {"n": event, "share": _share(event, len(b)),
                             "families": sorted({str(r.get("family") or "")
                                                 for r, a in zip(b, axes, strict=True)
                                                 if str(a.get("mechanism")) in EVENT_MECHANISMS
                                                 })[:12]},
        "pit": {"n_stamped": pit, "share": _share(pit, len(b)), "keys_searched": list(PIT_KEYS),
                "why": "share of intake rows carrying any point-in-time stamp"},
        "duplicates": duplicate_share(b, note),
    }


def cold_exploration(born: list[dict[str, Any]], vers: list[dict[str, Any]],
                     since: datetime) -> dict[str, Any]:
    """Share of the window's intake landing in grid cells that have NEVER produced a pass.

    THE GRID IS (asset_class, mechanism) AND THAT IS A CHOICE WITH A REASON. The verdict ledger
    carries `sym` and `family` and nothing else, so chart and session resolve to the axis
    registry's defaults for every judged row. A grid including them would mark every born cell
    carrying a real session as cold BY CONSTRUCTION, and a floor that is always met tells the desk
    nothing. Two axes both sources can actually supply is the honest grid.
    """
    warm: set[str] = set()
    seen: set[str] = set()
    for r in vers:
        a = axes_of(r.get("sym") or r.get("symbol"), r.get("family"))
        key = f"{a.get('asset_class')}|{a.get('mechanism')}"
        seen.add(key)
        if r.get("passed") is True:
            warm.add(key)
    b = [r for r in born if r.get("_t") is not None and r["_t"] >= since]
    cold = 0
    for r in b:
        a = axes_of(r.get("symbol"), r.get("family"), r.get("params"))
        if f"{a.get('asset_class')}|{a.get('mechanism')}" not in warm:
            cold += 1
    floor = 0.20
    try:
        import negative_knowledge as nk
        floor = float(nk.EXPLORE_FLOOR)
    except Exception:
        pass
    share = _share(cold, len(b))
    return {"cold_share": share, "n_cold": cold, "n_born": len(b), "explore_floor": floor,
            "under_floor": bool(share is not None and share < floor),
            "grid": "asset_class|mechanism", "n_grid_cells_seen": len(seen),
            "n_grid_cells_warm": len(warm), "status": "MEASURED" if b else "UNMEASURED",
            "why": "a grid cell is COLD until a verdict in it has PASSED. A machine that only "
                   "generates where it has already succeeded is a fixed point of its own history, "
                   "so this share is floored, never optimised away."}


def _msg(code: str, trigger: str, measured: Any, instruction: str, fired: bool) -> dict[str, Any]:
    return {"code": code, "trigger": trigger, "measured": measured, "instruction": instruction,
            "fired": bool(fired)}


def messages(w: dict[str, Any], cold: dict[str, Any],
             window: str = WINDOWS[0][0]) -> list[dict[str, Any]]:
    """The seven upstream messages. Each carries its reading; none is published without one.

    `window` is stamped on every message because the reading came from ONE window and a consumer
    must be able to see which: a share measured over seven days is a standing state, the same
    share over one day is this morning.
    """
    dup, bl = w["duplicates"].get("share"), w["backlog"]
    ck = w["failure_mix"].get("cost_killed_share")
    conc = w["concentration"].get("fx_h1_asia_share")
    ev, pit = w["event_mechanisms"].get("share"), w["pit"].get("share")
    xa, cap = w["cross_asset_novelty"].get("share"), bl.get("capacity_cells") or 0
    out = [
        _msg("too_many_duplicates", f"duplicate share > {DUP_SHARE_TRIGGER}",
             {"share": dup, "basis": w["duplicates"].get("basis")},
             "the same rule is being re-enqueued: generators must diff against the registry's "
             "content hash before donating, and spend the saved cells on an unvisited grid cell",
             dup is not None and dup > DUP_SHARE_TRIGGER),
        _msg("too_many_cost_killed",
             f"cost_killed share of classified failures > {COST_KILLED_TRIGGER}",
             {"share": ck, "by_class": w["failure_mix"].get("by_class")},
             "prefer lower-frequency charts / limit entries: the edge is real often enough to "
             "reach the cost gates and is being spent on turnover",
             ck is not None and ck > COST_KILLED_TRIGGER),
        _msg("too_much_fx_h1_asia", f"fx x H1 x asia share of intake > {CONCENTRATION_TRIGGER}",
             {"share": conc, "top_grid_cells": w["concentration"].get("top_grid_cells"),
              "top3_grid_share": w["concentration"].get("top3_grid_share")},
             "the compiler's novelty gate raises the bar for that cell; scouts and engines prefer "
             "other cells -- another chart, another session, another asset class",
             conc is not None and conc > CONCENTRATION_TRIGGER),
        _msg("not_enough_event_mechanisms",
             f"event / forced-flow share of intake < {EVENT_SHARE_TRIGGER}",
             {"share": ev, "n": w["event_mechanisms"].get("n")},
             "mine mechanisms with a DATED PAYER -- releases, fixings, index and futures rolls, "
             "close hedging flow -- which do not need the counterparty to be wrong",
             ev is not None and ev < EVENT_SHARE_TRIGGER),
        _msg("weak_pit_compliance", f"intake rows carrying a point-in-time stamp < {PIT_TRIGGER}",
             {"share": pit, "keys": list(PIT_KEYS)},
             "every intake row must carry available_time: an unstamped row cannot be judged "
             "point-in-time, and a certificate built on one is uncashable",
             pit is not None and pit < PIT_TRIGGER),
        _msg("weak_cross_asset_novelty",
             f"intake outside the top-3 asset classes < {CROSS_ASSET_TRIGGER}",
             {"share": xa, "top3": w["cross_asset_novelty"].get("top3_asset_classes")},
             "hunt the classes the docket is thin in -- metals, energy, indices, bonds, soft "
             "commodities -- a trial spent there costs the same and buys independent breadth",
             xa is not None and xa < CROSS_ASSET_TRIGGER),
        _msg("backlog_growing", f"backlog rose over the window AND exceeds "
                                f"{BACKLOG_CAPACITY_MULTIPLE}x the cells judged in it",
             {"backlog": bl.get("born_minus_judged"), "prior": bl.get("prior_window"),
              "capacity_cells": cap, "multiple": bl.get("over_capacity_multiple")},
             "READY_PRIORITY only: the exchange serves the top-scored, the rest wait. Generate no "
             "less -- order the queue by score and let the tail sit until capacity frees",
             bool(bl.get("growing") and cap > 0
                  and bl.get("born_minus_judged", 0) > BACKLOG_CAPACITY_MULTIPLE * cap)),
    ]
    if cold.get("under_floor"):
        out.append(_msg("cold_exploration_under_floor",
                        f"cold-cell share of intake < EXPLORE_FLOOR ({cold.get('explore_floor')})",
                        {"cold_share": cold.get("cold_share"), "grid": cold.get("grid")},
                        "raise the share of cells generated in grid cells that have never "
                        "produced a pass: the floor is what lets every prior here be wrong "
                        "recoverably", True))
    return [{**m, "window": window} for m in out]


def priors(vers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Jeffreys-smoothed p_edge priors per (family, chart, asset_class) bucket.

    Computed on EVERY verdict the ledger holds rather than on a window: a prior is what the desk
    KNOWS, and discarding last week's judgements to make it recent would trade evidence for
    freshness. Each row publishes its last verdict's stamp so a consumer can see the age.
    """
    buckets: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(
        lambda: {"n": 0, "pass": 0, "classes": Counter(), "gates": Counter(), "last": None})
    for r in vers:
        if r.get("passed") is None:
            continue
        fam = str(r.get("family") or UNKNOWN)
        a = axes_of(r.get("sym") or r.get("symbol"), fam)
        b = buckets[(fam, str(a.get("chart") or UNKNOWN), str(a.get("asset_class") or UNKNOWN))]
        b["n"] += 1
        if r.get("passed") is True:
            b["pass"] += 1
        else:
            gate = str(r.get("terminal_gate") or UNKNOWN)
            b["gates"][gate] += 1
            cls = gate_class(gate)
            if cls:
                b["classes"][cls] += 1
        t = r.get("_t")
        if t is not None and (b["last"] is None or t > b["last"]):
            b["last"] = t
    out: list[dict[str, Any]] = []
    for (fam, chart, klass), b in sorted(buckets.items(), key=lambda kv: -kv[1]["n"]):
        if b["n"] < MIN_BUCKET_JUDGED:
            continue
        n_cls = sum(b["classes"].values())
        dom = b["classes"].most_common(1)
        out.append({
            "memory_key": f"prior:{fam}|{chart}|{klass}", "family": fam, "chart": chart,
            "asset_class": klass, "n_judged": b["n"], "n_passed": b["pass"],
            "p_edge_prior": round((b["pass"] + 0.5) / (b["n"] + 1.0), 6),
            "failure_class_shares": ({k: round(n / n_cls, 4) for k, n in b["classes"].items()}
                                     if n_cls else {}),
            "dominant_failure_class": dom[0][0] if dom else None,
            "terminal_gates": dict(b["gates"].most_common(5)),
            "last_verdict_at": (None if b["last"] is None
                                else b["last"].isoformat(timespec="seconds")),
            "jeffreys": "p = (passed + 0.5) / (judged + 1)"})
    return out


#: `research_memory.result` ON THE REPLICATED FILE IS CHECK-CONSTRAINED and the fresh schema is
#: NOT. Measured 2026-09-17: the restored registry declares
#: `result TEXT NOT NULL CHECK (result IN ('pending','success','failure'))`, while `CANON`'s DDL
#: -- the one a test's tmp file is built from -- declares a plain TEXT column. So the first real
#: run wrote 0 of 27 priors with `IntegrityError: CHECK constraint failed` while every test was
#: green. The vocabulary is the FILE'S, not this organ's, and a bucket's result is read in it: a
#: bucket that has produced a pass is a `success`, one that has judged its floor and produced
#: none is a `failure`. Nothing is invented and nothing is NULL (the column is NOT NULL too).
_RESULT_VOCAB = ("pending", "success", "failure")


def write_priors(rows: list[dict[str, Any]], at: str) -> dict[str, Any]:
    """Upsert every bucket into the canonical registry's research memory. Idempotent by key."""
    if _registry is None:
        return {"written": 0, "status": "UNMEASURED",
                "why": "libs.moat.registry unavailable on this tree"}
    written = 0
    try:
        for r in rows:
            _registry.remember(
                "candidate_prior",
                f"{r['family']} on {r['chart']} in {r['asset_class']}: {r['n_passed']}/"
                f"{r['n_judged']} judged cells passed the ten gates; dominant failure "
                f"{r['dominant_failure_class'] or 'UNCLASSIFIED'}",
                kind="candidate_prior", memory_key=r["memory_key"],
                result=("success" if r["n_passed"] > 0 else "failure"),
                failure_cause=r["dominant_failure_class"],
                metrics={**{k: v for k, v in r.items() if k != "memory_key"}, "at": at},
                payload={"source": "gauntlet_backpressure", "artifact": _rel(OUT)})
            written += 1
        return {"written": written, "status": "OK",
                "read_back_with": 'registry.memories(category="candidate_prior")'}
    except Exception as exc:
        return {"written": written, "status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}


def bandit_view(rows: list[dict[str, Any]], w: dict[str, Any]) -> dict[str, Any]:
    """The window in the bandit's own arm vocabulary, plus the feedback that has no inbound path."""
    out: dict[str, Any] = {"module": "libs/research/bandit.py",
                           "evidence_path": "bandit.evidence(graph_rows) -- pure, read-only"}
    try:
        from libs.research import bandit
        ev = bandit.evidence([{k: v for k, v in r.items() if k != "_t"} for r in rows])
        arms = {a: {k: d[k] for k in ("born", "failed", "certified", "p_survivor", "group")}
                for a, d in ev.items() if isinstance(d, dict)}
    except Exception as exc:
        return {**out, "status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
    return {**out, "status": "MEASURED", "arms": arms, "intended_feedback": {
        "shape": "per-arm worth multiplier from the window's failure mix",
        "failure_class_shares": w["failure_mix"].get("class_shares") or {},
        "arms_seen_in_window": {a: {"born_in_window": d["born"], "p_survivor": d["p_survivor"]}
                                for a, d in arms.items() if d["born"]},
        "applied": False,
        "why": "the bandit accepts graph rows and returns a posterior; it has no API that "
               "RECEIVES an external evidence row, and its only file-shaped inbound worth path is "
               "data/research_marginal.json, whose writer is research_pnl.py. Two writers on one "
               "artifact is how an artifact goes stale with nobody at fault, so this is "
               "published, not written.",
        "to_wire": "either bandit.evidence grows a `feedback_by_arm` argument, or research_pnl "
                   "folds this report's class shares into worth_by_arm"}}


def build(now: datetime | None = None) -> dict[str, Any]:
    at = now or _now()
    note: dict[str, str] = {}
    born = born_cells(_read_jsonl(GRAPH, note))
    vers = verdicts(_read_jsonl(GATE_LEDGER, note))
    windows = {name: window_measure(born, vers, at, hours, note) for name, hours in WINDOWS}
    primary = windows[WINDOWS[0][0]]
    # THE MESSAGES ARE MEASURED ON ONE WINDOW AND IT IS NAMED. The first window with any intake
    # wins: this desk's mining is bursty -- measured 2026-09-17, the graph's last birth was seven
    # days before the sweep that judged it -- and an organ that goes silent every time the miners
    # pause for a day tells nobody anything, while mixing windows inside one message set would
    # hide which reading came from where. Every message carries its `window`.
    order = [n for n, _ in WINDOWS]
    msg_window = next((n for n in order if windows[n]["intake"]["born_cells"]), order[0])
    msg_hours = dict(WINDOWS)[msg_window]
    cold = cold_exploration(born, vers, at - timedelta(hours=msg_hours))
    pri = priors(vers)
    queue: dict[str, Any] = {"status": "UNMEASURED", "why": "libs.moat.registry unavailable"}
    grid_cells: Any = None
    if _registry is not None:
        try:
            queue = {"status": "MEASURED", "by_origin_status": _registry.queue_depth()}
            grid_cells = len(_registry.grid_coverage())
        except Exception as exc:
            queue = {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
    primary["backlog"]["registry_queue_depth"] = queue
    primary["backlog"]["registry_grid_cells"] = grid_cells
    unmeasured = {k: v for k, v in note.items() if v != "READ"}
    if not born:
        unmeasured["hypothesis_graph"] = "NO_BORN_CELLS"
    if not vers:
        unmeasured["gate_verdict_ledger"] = "NO_VERDICTS"
    if queue.get("status") != "MEASURED":
        unmeasured["registry_queue_depth"] = str(queue.get("why"))
    if not primary["intake"]["born_cells"]:
        unmeasured["messages_intake"] = (
            f"no cell was born in the {order[0]} window; the intake-shaped messages "
            f"(duplicates, concentration, event mix, PIT, cross-asset novelty, cold share) are "
            + (f"measured on {msg_window} instead and every message says so"
               if msg_window != order[0] else
               "UNMEASURED rather than clear -- no window in this report holds an intake"))
    msgs = messages(windows[msg_window], cold, msg_window)
    return {
        "at": at.isoformat(timespec="seconds"), "windows": windows, "messages": msgs,
        "messages_window": msg_window,
        "fired": [m["code"] for m in msgs if m["fired"]],
        "priors": pri, "priors_written": 0,
        "prior_contract": {
            "read_with": 'registry.memories(category="candidate_prior")',
            "memory_key": "prior:<family>|<chart>|<asset_class>",
            "metrics": ["family", "chart", "asset_class", "n_judged", "n_passed", "p_edge_prior",
                        "failure_class_shares", "dominant_failure_class", "terminal_gates",
                        "last_verdict_at", "at"],
            "min_judged": MIN_BUCKET_JUDGED,
            "consumers": "the discovery compiler and the moat engines (read-only; nothing here "
                         "reaches into them)",
            "limitation": "the verdict ledger carries no chart, so the chart axis reads the "
                          "docket's declared default (H1) for every bucket until the gauntlet "
                          "stamps one. The bucket is real; the chart in its key is the default, "
                          "and a consumer must not read it as a measurement."},
        "gate_failure_class_table": {k: v for k, v in GATE_FAILURE_CLASS.items() if k},
        "failure_classes_no_gate_produces": sorted(
            set(getattr(_registry, "FAILURE_CLASSES", ()))
            - {v for v in GATE_FAILURE_CLASS.values() if v}) if _registry else [],
        "cold_share": cold.get("cold_share"), "cold": cold,
        "capacity": capacity(note, at),
        "bandit": bandit_view([r for r in born if r.get("_t") is not None
                               and r["_t"] >= at - timedelta(hours=WINDOWS[-1][1])], primary),
        "unmeasured": unmeasured,
        "rule": "the gauntlet talks back: the miners change what they generate, and every failure "
                "class moves a prior, while cold exploration keeps its floor",
    }


def _atomic_write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return path


def write(doc: dict[str, Any], path: Path | None = None) -> Path:
    return _atomic_write(path or OUT, json.dumps(doc, indent=1, default=str))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and print; write no report and no prior")
    a = ap.parse_args(argv)
    doc = build()
    w = doc["windows"][WINDOWS[0][0]]
    print(f"gauntlet backpressure {doc['at']}")
    for name, _ in WINDOWS:
        x = doc["windows"][name]
        print(f"  {name:>4}  intake {x['intake']['per_hour']:>8.2f}/h   judged "
              f"{x['testing']['per_hour']:>8.2f}/h   backlog "
              f"{x['backlog']['born_minus_judged']:>7d}   dup {x['duplicates'].get('share')}"
              f"   fx/H1/asia {x['concentration'].get('fx_h1_asia_share')}")
    print(f"  failure classes: {w['failure_mix']['by_class']}")
    print(f"  cold share {doc['cold_share']} vs floor {doc['cold']['explore_floor']}"
          f"{'  UNDER FLOOR' if doc['cold']['under_floor'] else ''}")
    for m in doc["messages"]:
        if m["fired"]:
            print(f"  ! {m['code']:<30} {m['measured']}\n    -> {m['instruction'][:120]}")
    print(f"  priors: {len(doc['priors'])} bucket(s) at >= {MIN_BUCKET_JUDGED} judged")
    if a.dry_run:
        print("  --dry-run: nothing written")
        return 0
    res = write_priors(doc["priors"], doc["at"])
    doc["priors_written"] = res.get("written", 0)
    doc["prior_write"] = res
    print(f"-> {write(doc)}  ({doc['priors_written']} prior(s) into the registry)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
