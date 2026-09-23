"""W16 -- A SURVIVOR IS THE ROOT OF A FAMILY, NOT A CELL, AND THE FAMILY'S COVERAGE IS MEASURED.

THE PRINCIPAL, 2026-09-16 (ledger item W16, the "permanent evolving organization" layer): every
discovery spawns descendants -- horizontal (assets), temporal (charts), conditional (regimes),
execution -- so the desk's survivors are the ROOTS OF FAMILIES rather than lucky single points.
The ledger's own next_step names this file.

WHAT THE DESK HAD, AND WHY IT IS NOT THIS. 58 certificates, three promoted sleeves and 653 forward
clocks, each one a SINGLE CELL: one instrument, one chart, one session, one exit. `breadth_sweep`
and the compiler's `expand_axes` do spawn chart and session variants -- of EVERY docket row,
indiscriminately -- which is breadth over the docket and says nothing about the neighbourhood of
the cells that WORK. Nothing here has ever asked what sits one step from a certificate, and a
survivor with no measured neighbourhood cannot be told from an overfit: if the mechanism is real
the cell beside it pays too, and if nothing beside it pays, the search was the edge.

ONE AXIS, NEVER TWO. A descendant differs from its root on exactly ONE declared axis. Two moves at
once and a failure names nothing -- the desk could not tell the instrument from the exit -- and the
family's coverage stops being a coverage of anything. Every refusal below protects that property:
the D1 rung is refused for a root carrying a session (daily bars have none, so the move would be
two), a chart neighbour is refused where the instrument has no bars (UNMEASURED, not tested), and
`state` is refused outright because no registered family on this tree reads a state tag -- the
gauntlet filters params to the family's signature, so the tag would be dropped and the
"descendant" would be its parent wearing a label.

THE SIX AXES, each 1-3 steps wide:

    instrument    same asset class (`axis_registry.instruments_by_class`, which is
                  `universe_policy` and therefore NEVER a single-name equity), ranked by 60-day H1
                  return correlation, alphabetical where a leg is not priced.
    session       the adjacent windows of `family_call.SESSIONS` (asia 0-8, london 8-16, ny 14-22,
                  in window-start order) plus the unconditioned `all`.
    horizon       the adjacent chart on M5 < M15 < H1 < H4 < D1, only where the bars exist.
    exit          the family's OWN knobs, read from its signature: the holding window halved and
                  doubled, and the trailing stop toggled where a family exposes one.
    state         a {high_vol, low_vol} tag -- skipped and COUNTED, see above.
    cross_market  the mechanism on the nearest instrument of ANOTHER non-equity class, by
                  |correlation| (an inverse leg is as near as a positive one).

THE GRAPH IS THE FAMILY'S MEMORY. A descendant already in `hypothesis_graph.jsonl` is never
re-donated -- it was born, and its fate belongs to the family record rather than to a second trial.
That is also what makes coverage honest: tested/possible per axis, where possible is the live
neighbourhood and tested is what the desk has actually spent something on. An axis with no
enumerable neighbour is UNMEASURED with a reason, never a covered zero (L1.28a).

NOTHING HERE PROMOTES, SIZES OR CERTIFIES. Every descendant re-enters at the ordinary intake as an
EXACT_RECIPE candidate, inherits none of its parent's credibility and walks the same ten gates.

    python desks/mt5/research/descendants.py [--dry-run] [--max-per-root 4] [--budget-s 240]
"""
from __future__ import annotations

import argparse
import inspect
import json
import math
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import hypothesis_graph as hg  # noqa: E402
from research import axis_registry as ar  # noqa: E402

SLEEVES = DESK / "data" / "sleeves.json"
SHADOW = DESK / "reports" / "shadow" / "shadow_state.json"
SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
GRAPH_LEDGER = DESK / "data" / "hypothesis_graph.jsonl"
UNIVERSE = DESK / "data" / "universe"
RECORD = DESK / "data" / "descendants.json"
OUT = DESK / "reports" / "DESCENDANTS.json"

#: The intake seat. A COLON IS NOT A PATH CHARACTER on the box that trades and the seat becomes a
#: directory, so the axis rides on each row's own `source` (`descendants:<axis>`), never here.
SEAT = "descendants"
DESCENDANT_AXES = ("instrument", "session", "horizon", "exit", "state", "cross_market")
#: The holding ladder. M1 and M30 exist on this tree but are not RUNGS of it, and a root off the
#: ladder gets no horizon descendant rather than an invented one.
CHART_LADDER = ("M5", "M15", "H1", "H4", "D1")
TTL_KEYS = ("ttl_bars", "hold_bars", "max_hold")
STATE_TAGS = ("high_vol", "low_vol")
STATE_PARAMS = ("state", "vol_state", "market_state", "regime")
#: Steps per axis: three IS the neighbourhood of a cell on one axis; more is a sweep. And new
#: descendants one root may donate per run -- the family grows every hour, not in one write.
MAX_NEIGHBOURS = 3
MAX_PER_ROOT = 4
BUDGET_S = 240.0
#: Instruments of one class ranked by correlation in a run: each costs a parquet read, and the box
#: holding the live terminal has 8 GB.
POOL_MAX = 24
CORR_DAYS = 60
MIN_CORR_BARS = 120
#: Forward observations below which a clock is an ENROLMENT, not evidence, and spawns nothing; and
#: the statuses that mean the clock has STOPPED, so its cell is history rather than a live root.
MATURE_FORWARD_N = 5
DEAD_CLOCK = ("RETIRED", "REFUSED", "BLOCKED", "VOID", "ORPHAN")
MAX_RECORDS = 500

DONATED = "DONATED"
LANE_RANK = {"LIVE": 3, "STANDBY": 2, "FORWARD": 1, "CERTIFIED": 1}
RULE = ("every survivor is the root of a family; each descendant moves along one axis; "
        "the family's coverage of the axes is measured")


# ------------------------------------------------------------------ tolerant reading
def _read_json(path: Path, note: dict[str, str]) -> Any:
    """Parse `path`, or record exactly why it produced nothing. Never raises."""
    try:
        doc = json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError) as exc:
        note[path.name] = ("ABSENT" if isinstance(exc, FileNotFoundError)
                           else f"UNREADABLE({type(exc).__name__})")
        return None
    note[path.name] = "READ"
    return doc


def graph_fates(path: Path | None = None) -> dict[str, str]:
    """`cell_id -> the last fate the ledger recorded`, through the graph's OWN reader.

    `Graph.current()` already carries the append-only semantics (last row per id wins) a local
    parse would have to re-derive, and the id contract is the graph's too -- a descendant whose id
    does not join the ledger's is a second spelling of a cell the desk has already judged.
    """
    try:
        return {str(k): str(r.get("fate") or hg.BORN)
                for k, r in hg.Graph(path or GRAPH_LEDGER).current().items()}
    except (OSError, ValueError):
        return {}


# ------------------------------------------------------------------ families and specs
_REGISTRY: dict[str, tuple[Any, dict[str, Any]]] | None = None


def _registry() -> dict[str, tuple[Any, dict[str, Any]]]:
    """family -> (callable, declared defaults), read once. Empty when nothing is importable."""
    global _REGISTRY
    if _REGISTRY is None:
        out: dict[str, tuple[Any, dict[str, Any]]] = {}
        try:
            from mt5desk import families as fam_mod
            from mt5desk import families_orthogonal as fo
            for name, e in (getattr(fam_mod, "FAMILY_REGISTRY", {}) or {}).items():
                fn, d = (e.get("func"), e.get("defaults")) if isinstance(e, dict) else (e, None)
                if callable(fn):
                    out[str(name)] = (fn, dict(d) if isinstance(d, dict) else {})
            for name, fn in (getattr(fo, "ORTHOGONAL_FAMILIES", {}) or {}).items():
                if callable(fn):
                    out.setdefault(str(name), (fn, {}))
        except Exception:
            out = {}
        _REGISTRY = out
    return _REGISTRY


def family_knobs(family: str) -> tuple[frozenset[str], dict[str, Any]]:
    """(the names the family's signature accepts, its declared defaults).

    The signature is the authority on what an exit or state move may touch -- the gauntlet filters
    a cell's params to it -- and the defaults let a knob the root never set still be moved.
    """
    entry = _registry().get(str(family))
    if entry is None:
        return frozenset(), {}
    try:
        names = list(inspect.signature(entry[0]).parameters)[1:]
    except (TypeError, ValueError):
        return frozenset(), dict(entry[1])
    return frozenset(n for n in names if n != "side"), dict(entry[1])


def spec(symbol: Any, family: Any, params: dict[str, Any] | None, chart: str,
         session: str) -> dict[str, Any]:
    """The canonical executable spec: `timeframe` written only when it is not H1 and `session`
    only when it is not `all` -- the docket's own convention (`breadth_sweep`), which is what makes
    a descendant's id JOIN the graph's rows rather than sit beside them as a second spelling."""
    p = {k: v for k, v in (params or {}).items() if k not in ("timeframe", "session")}
    if chart and chart != "H1":
        p["timeframe"] = chart
    if session and session != "all":
        p["session"] = session
    return {"symbol": str(symbol or "").upper(), "family": str(family or ""), "params": p,
            "chart": chart or "H1", "session": session or "all"}


def cell_id(s: dict[str, Any]) -> str:
    """The graph's own id for a spec. The contract is `hypothesis_graph`'s, not this organ's."""
    return hg.node_id(s["symbol"], s["family"], s["params"])


def _call_params(row: dict[str, Any], family: str) -> dict[str, Any]:
    """The keys of `row` this family actually takes -- a sleeve row is mostly bookkeeping."""
    args = family_knobs(family)[0]
    return {k: v for k, v in row.items()
            if k in args and isinstance(v, (int, float, str, bool, list))}


def _has_bars(symbol: str, chart: str) -> bool:
    return (UNIVERSE / f"{symbol}_{chart or 'H1'}.parquet").exists()


# ------------------------------------------------------------------ the roots
def collect_roots(note: dict[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(roots, unmeasured): LIVE and STANDBY sleeves, ten-gate certificates, and MATURED forward
    clocks. A clock below `MATURE_FORWARD_N` is an enrolment, and spawning from one would spend the
    docket on the neighbourhood of a cell nothing is yet known about. Ranked LIVE first and then by
    forward evidence, so the strongest survivor spawns before the budget runs out."""
    roots: dict[str, dict[str, Any]] = {}
    unmeasured: list[dict[str, Any]] = []
    wrong_lane: set[str] = set()

    def add(source: str, lane: str, s: dict[str, Any], n: int) -> None:
        if not s["family"] or not s["symbol"]:
            return
        # THE TWO-LANE DOOR, AT THE SOURCE. A single-name equity is traded on news and earnings
        # reaction, never hunted for statistical hypotheses -- so its cell is not the root of a
        # statistical family either. `donate` would refuse the children anyway; refusing the
        # PARENT is what stops the slots and the report being spent on rows nothing can admit.
        if not ar.may_hypothesise(s["symbol"]):
            wrong_lane.add(s["symbol"])
            return
        row = {"root_id": cell_id(s), "source": source, "lane": lane, "symbol": s["symbol"],
               "family": s["family"], "params": dict(s["params"]), "chart": s["chart"],
               "session": s["session"], "forward_n": int(n), "spec": s}
        prev = roots.get(row["root_id"])
        if prev is None or (LANE_RANK.get(lane, 0), int(n)) > (LANE_RANK.get(prev["lane"], 0),
                                                              prev["forward_n"]):
            roots[row["root_id"]] = row

    clocks = _read_json(SHADOW, note)
    #: (symbol, family) -> the largest forward n any clock holds, so a CERTIFIED root ranks on
    #: forward evidence it actually has rather than on the certificate alone.
    forward_n: dict[tuple[str, str], int] = {}
    keyless = 0
    for key, row in (clocks if isinstance(clocks, dict) else {}).items():
        if not isinstance(row, dict):
            continue
        parsed = ar.parse_shadow_key(str(key))
        sym, fam = str(parsed["symbol"] or "").upper(), str(parsed["family"] or "")
        n, status = int(row.get("n") or 0), str(row.get("status") or "").upper()
        if sym and fam:
            forward_n[(sym, fam)] = max(forward_n.get((sym, fam), 0), n)
        if n < MATURE_FORWARD_N or any(d in status for d in DEAD_CLOCK):
            continue
        if not fam:
            keyless += 1
            continue
        add("shadow_state", "FORWARD", spec(sym, fam, {}, ar.normalise_chart(row.get("timeframe")),
                                            ar.normalise_session(parsed["session"])), n)
    if keyless:
        unmeasured.append({"what": "matured forward clocks with no family in their key",
                           "n": keyless, "why": "the key names a symbol and a selector only: the "
                           "mechanism to inherit is unknown, so no descendant can be built"})

    doc = _read_json(SURVIVORS, note)
    for row in ((doc.get("survivors") if isinstance(doc, dict) else None) or {}).values():
        sp = row.get("shadow_spec") if isinstance(row, dict) else None
        if not isinstance(sp, dict):
            continue
        sym = str(sp.get("symbol") or row.get("sym") or "").upper()
        fam = str(sp.get("family") or "")
        raw = sp.get("params")
        params: dict[str, Any] = raw if isinstance(raw, dict) else {}
        add("UNIVERSAL_SURVIVORS", "CERTIFIED",
            spec(sym, fam, _call_params(params, fam),
                 ar.normalise_chart(sp.get("timeframe") or params.get("timeframe")),
                 ar.normalise_session(sp.get("selector") or sp.get("session"))),
            forward_n.get((sym, fam), 0))

    doc = _read_json(SLEEVES, note)
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    for row in rows if isinstance(rows, list) else []:
        lane = str(row.get("status") or "").upper() if isinstance(row, dict) else ""
        if lane not in ("LIVE", "STANDBY"):
            continue
        fam = str(row.get("family") or "")
        add("sleeves", lane, spec(row.get("symbol"), fam, _call_params(row, fam),
                                  ar.normalise_chart(row.get("timeframe")),
                                  ar.normalise_session(row.get("session") or row.get("selector"))),
            int(row.get("shadow_n") or 0))

    ordered = sorted(roots.values(),
                     key=lambda r: (-LANE_RANK.get(r["lane"], 0), -r["forward_n"], r["root_id"]))
    if wrong_lane:
        unmeasured.append({"what": "roots refused by the two-lane mandate", "n": len(wrong_lane),
                           "symbols": sorted(wrong_lane)[:12], "why": "these instruments are "
                           "traded on news and earnings reaction, never hunted for statistical "
                           "hypotheses, so their cells are not the roots of statistical families"})
    odd = sorted({r["session"] for r in ordered} - {"all", *session_ladder()})
    if odd:
        unmeasured.append({"what": "roots on a session with no window", "sessions": odd,
                           "why": "`session_window` returns None for these so the filter keeps "
                           "every bar; the tag is inherited verbatim rather than rewritten, "
                           "because rewriting it would move a second axis"})
    return ordered, unmeasured


# ------------------------------------------------------------------ the neighbourhood
def session_ladder() -> tuple[str, ...]:
    """The windowed sessions in window-start order -- the desk's own table, never a copy."""
    try:
        from mt5desk.family_call import SESSIONS
    except Exception:
        return ("asia", "london", "ny")
    return tuple(k for _, k in sorted((w[0], k) for k, w in SESSIONS.items()
                                      if isinstance(w, tuple) and len(w) == 2))


def _returns(symbol: str) -> pd.Series | None:
    """The last `CORR_DAYS` days of H1 log returns, or None when the instrument is not priced."""
    try:
        df = pd.read_parquet(UNIVERSE / f"{symbol}_H1.parquet", columns=["close"])
    except (OSError, ValueError, ImportError, KeyError):
        return None
    if df.empty:
        return None
    idx = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True, errors="coerce"))
    s = pd.Series(np.asarray(df["close"], dtype=float), index=idx)
    s = s[~s.index.isna()].dropna()
    s = s[s > 0].tail(CORR_DAYS * 24)
    if s.size < MIN_CORR_BARS:
        return None
    r = np.log(s / s.shift(1)).dropna()
    return r if r.size >= MIN_CORR_BARS else None


class Neighbourhood:
    """The desk's class map plus a correlation cache, read once per run and shared by the roots."""

    def __init__(self, pool_max: int = POOL_MAX) -> None:
        self.by_class = {k: list(v) for k, v in ar.instruments_by_class().items() if k}
        self.pool_max = int(pool_max)
        self._ret: dict[str, pd.Series | None] = {}
        self._corr: dict[tuple[str, str], float | None] = {}
        self.unpriced: set[str] = set()

    def returns(self, symbol: str) -> pd.Series | None:
        if symbol not in self._ret:
            self._ret[symbol] = _returns(symbol)
            if self._ret[symbol] is None:
                self.unpriced.add(symbol)
        return self._ret[symbol]

    def corr(self, a: str, b: str) -> float | None:
        key = (a, b) if a <= b else (b, a)
        if key not in self._corr:
            ra, rb = self.returns(a), self.returns(b)
            value: float | None = None
            if ra is not None and rb is not None:
                x, y = ra.align(rb, join="inner")
                c = float(x.corr(y)) if x.size >= MIN_CORR_BARS else float("nan")
                value = c if math.isfinite(c) else None
            self._corr[key] = value
        return self._corr[key]

    def nearest(self, symbol: str, pool: list[str], limit: int = MAX_NEIGHBOURS,
                absolute: bool = False) -> list[str]:
        """Nearest by 60-day return correlation, ALPHABETICAL where it cannot be measured."""
        pool = [s for s in dict.fromkeys(pool) if s != symbol][: self.pool_max]
        scored = {s: self.corr(symbol, s) for s in pool}
        ranked = sorted((s for s in pool if scored[s] is not None),
                        key=lambda s: (-abs(scored[s] or 0.0) if absolute else -(scored[s] or 0.0),
                                       s))
        return (ranked + sorted(s for s in pool if scored[s] is None))[: max(0, int(limit))]


def _step(axis: str, s: dict[str, Any], why: str) -> dict[str, Any]:
    return {"axis": axis, "spec": s, "cell_id": cell_id(s), "why": why}


def neighbours(root: dict[str, Any], ctx: Neighbourhood,
               ) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    """(axis -> its 1-3 nearest neighbours, axis -> why it could not be walked).

    Every neighbour differs from `root` on exactly ONE axis, and an axis that cannot be walked is
    NAMED rather than counted as covered.
    """
    sym, fam = root["symbol"], root["family"]
    params, chart, session = root["params"], root["chart"], root["session"]
    out: dict[str, list[dict[str, Any]]] = {a: [] for a in DESCENDANT_AXES}
    skip: dict[str, str] = {}
    klass = ar.asset_class_of(sym)

    pool = [s for s in ctx.by_class.get(klass, []) if s != sym and _has_bars(s, chart)]
    for other in ctx.nearest(sym, pool):
        c = ctx.corr(sym, other)
        out["instrument"].append(_step("instrument", spec(other, fam, params, chart, session),
                                       f"same class ({klass}); 60d corr with {sym} "
                                       + (f"{c:+.2f}" if c is not None else "UNMEASURED (a-z)")))
    if not pool:
        skip["instrument"] = f"no other hypothesis-lane {klass!r} instrument holds {chart} bars"

    ladder = session_ladder()
    if chart == "D1":
        skip["session"] = "daily bars carry no session, so the window is not an axis here"
    else:
        i = ladder.index(session) if session in ladder else -1
        cand = ([*ladder[max(0, i - 1):i], *ladder[i + 1:i + 2], "all"] if i >= 0
                else [*ladder, "all"])
        for other in [c for c in dict.fromkeys(cand) if c != session][:MAX_NEIGHBOURS]:
            out["session"].append(_step("session", spec(sym, fam, params, chart, other),
                                        f"the window beside {session} in `family_call.SESSIONS`"
                                        if other != "all" else "the same rule, no session window"))

    if chart not in CHART_LADDER:
        skip["horizon"] = f"{chart} is not a rung of {' < '.join(CHART_LADDER)}"
    else:
        i = CHART_LADDER.index(chart)
        for other in [*CHART_LADDER[max(0, i - 1):i], *CHART_LADDER[i + 1:i + 2]]:
            if not _has_bars(sym, other):
                skip["horizon"] = f"{sym} has no {other} bars here: UNMEASURED, not a cell"
            elif other == "D1" and session != "all":
                skip["horizon"] = ("the D1 rung would drop this root's session too, and a "
                                   "descendant moves ONE axis")
            else:
                out["horizon"].append(_step("horizon", spec(sym, fam, params, other, session),
                                            f"the chart beside {chart} on the holding ladder"))

    args, defaults = family_knobs(fam)
    ttl_key = next((k for k in TTL_KEYS if k in args), "")
    base = params.get(ttl_key, defaults.get(ttl_key)) if ttl_key else None
    if isinstance(base, (int, float)) and not isinstance(base, bool) and base > 0:
        for mult, label in ((0.5, "half"), (2.0, "double")):
            value = max(1, round(float(base) * mult))
            if value != int(base):
                out["exit"].append(_step(
                    "exit", spec(sym, fam, {**params, ttl_key: value}, chart, session),
                    f"{label} the holding window ({ttl_key} {base} -> {value})"))
    if "trail" in args:
        on = bool(params.get("trail", defaults.get("trail", False)))
        out["exit"].append(_step("exit", spec(sym, fam, {**params, "trail": not on},
                                              chart, session),
                                 f"trailing stop {'off' if on else 'on'}"))
    if not out["exit"]:
        skip["exit"] = (f"{fam or 'the family'} exposes no holding window to move "
                        f"({', '.join(sorted(args)) or 'no readable signature'})")

    state_key = next((k for k in STATE_PARAMS if k in args), "")
    if not state_key:
        skip["state"] = (f"{fam or 'the family'} reads no state tag and the gauntlet filters "
                         "params to the signature: the tag would be dropped and the descendant "
                         "would be its own parent")
    for tag in STATE_TAGS if state_key else ():
        if params.get(state_key) != tag:
            out["state"].append(_step("state", spec(sym, fam, {**params, state_key: tag},
                                                    chart, session),
                                      f"the same rule conditioned on {tag}"))

    picks: list[tuple[float, str, dict[str, Any]]] = []
    for other_class in sorted(k for k in ctx.by_class if k != klass):
        near = ctx.nearest(sym, [s for s in ctx.by_class[other_class] if _has_bars(s, chart)],
                           limit=1, absolute=True)
        if near:
            c = ctx.corr(sym, near[0])
            picks.append((-abs(c) if c is not None else 0.0, other_class,
                          _step("cross_market", spec(near[0], fam, params, chart, session),
                                f"nearest {other_class} instrument to {sym} by |60d corr| "
                                + (f"{c:+.2f}" if c is not None else "UNMEASURED"))))
    out["cross_market"] = [p[2] for p in sorted(picks, key=lambda p: (p[0], p[1]))][:MAX_NEIGHBOURS]
    if not picks:
        skip["cross_market"] = (f"no other non-equity class holds {chart} bars here, so there is "
                                "no analogue to carry the mechanism to")
    return out, skip


# ------------------------------------------------------------------ the family record
def load_record(path: Path | None = None) -> dict[str, Any]:
    doc = _read_json(path or RECORD, {})
    if not isinstance(doc, dict) or not isinstance(doc.get("families"), dict):
        return {"at": "", "rule": RULE, "families": {}}
    return doc


def refresh(record: dict[str, Any], root: dict[str, Any], nb: dict[str, list[dict[str, Any]]],
            skip: dict[str, str], fates: dict[str, str], now: str) -> dict[str, Any]:
    """The root's family record, joined to the graph's fates and to TODAY's neighbourhood.

    A descendant is REALISED when the graph knows it or this organ donated it, and coverage counts
    those against the neighbourhood that exists now -- so a family whose axis widened reads as less
    covered rather than as finished."""
    stored = record.get("families", {}).get(root["root_id"]) or {}
    kept = {str(d.get("cell_id")): dict(d) for d in (stored.get("descendants") or [])
            if isinstance(d, dict) and d.get("cell_id")}
    coverage: dict[str, dict[str, int]] = {}
    for axis in DESCENDANT_AXES:
        steps = nb.get(axis) or []
        tested = 0
        for step in steps:
            cid, fate = step["cell_id"], fates.get(step["cell_id"])
            if fate is None and cid not in kept:
                continue
            tested += 1
            row = kept.get(cid) or {"born_at": now}
            row.update({"axis": axis, "spec": step["spec"], "cell_id": cid,
                        "fate": fate or str(row.get("fate") or DONATED)})
            kept[cid] = row
        coverage[axis] = {"tested": tested, "possible": len(steps)}
    possible = sum(c["possible"] for c in coverage.values())
    tested = sum(c["tested"] for c in coverage.values())
    return {"root_id": root["root_id"], "spec": root["spec"], "lane": root["lane"],
            "symbol": root["symbol"], "family": root["family"], "source": root["source"],
            "forward_n": root["forward_n"], "seen_at": now,
            "descendants": sorted(kept.values(), key=lambda d: (d["axis"], d["cell_id"])),
            "coverage": coverage,
            "coverage_overall": round(tested / possible, 4) if possible else None,
            "axes_unreachable": skip}


def record_donations(record: dict[str, Any], rows: list[dict[str, Any]], now: str) -> int:
    """Write what was just donated into the record, so the next run does not re-donate it."""
    n = 0
    for row in rows:
        lineage = row.get("lineage") or {}
        fam_row = record.get("families", {}).get(str(lineage.get("root")))
        cid = hg.node_id(str(row.get("symbol")), str(row.get("family")), row.get("params") or {})
        if not isinstance(fam_row, dict) or any(d.get("cell_id") == cid
                                                for d in fam_row["descendants"]):
            continue
        fam_row["descendants"].append({"axis": str(lineage.get("axis")), "cell_id": cid,
                                       "spec": row.get("spec_key") or {}, "born_at": now,
                                       "fate": DONATED})
        n += 1
    return n


# ------------------------------------------------------------------ what to donate
def pick(root: dict[str, Any], nb: dict[str, list[dict[str, Any]]], known: set[str],
         max_per_root: int) -> list[dict[str, Any]]:
    """At most `max_per_root` unborn neighbours, ROUND-ROBIN over the axes: taking the lists in
    order would spend a root's whole budget on instrument siblings and the family would grow along
    one axis forever, which is the single-cell failure this organ exists to end, one level up."""
    out: list[dict[str, Any]] = []
    for depth in range(MAX_NEIGHBOURS):
        if len(out) >= max_per_root or all(depth >= len(nb.get(a) or []) for a in DESCENDANT_AXES):
            break
        for axis in DESCENDANT_AXES:
            steps = nb.get(axis) or []
            if depth >= len(steps) or len(out) >= max_per_root:
                continue
            if steps[depth]["cell_id"] not in known:
                known.add(steps[depth]["cell_id"])
                out.append({**steps[depth], "root": root})
    return out


def rows_for(picked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Intake rows: EXACT_RECIPE candidates carrying the lineage that produced them."""
    from research.proposer_common import candidate
    rows = []
    for step in picked:
        s, axis, root = step["spec"], step["axis"], step["root"]
        row = candidate(f"{SEAT}:{axis}", s["symbol"], s["family"], dict(s["params"]),
                        mechanism=f"{ar.classify_family(s['family'])[0]}: inherited unchanged from "
                                  f"a {root['lane']} root; this cell moves ONE axis ({axis}) -- "
                                  f"{step['why']}",
                        title=f"{s['symbol']} {s['family']} {s['chart']}/{s['session']} -- {axis} "
                              f"descendant of {root['symbol']} ({root['lane']})",
                        evidence={"root_id": root["root_id"], "root_spec": root["spec"],
                                  "root_lane": root["lane"], "root_forward_n": root["forward_n"],
                                  "axis": axis, "why": step["why"], "rule": RULE})
        row.update({"parent": root["root_id"], "operator": f"descendant:{axis}", "spec_key": s,
                    "lineage": {"root": root["root_id"], "axis": axis,
                                "root_symbol": root["symbol"], "root_family": root["family"],
                                "root_lane": root["lane"]}})
        rows.append(row)
    return rows


# ------------------------------------------------------------------ build
def build(*, max_per_root: int = MAX_PER_ROOT, budget_s: float = BUDGET_S,
          ) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """(report, family record, rows to donate). Never raises on a missing input."""
    t0 = time.monotonic()
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    note: dict[str, str] = {}
    roots, unmeasured = collect_roots(note)
    fates = graph_fates()
    if not fates:
        unmeasured.append({"what": "the hypothesis graph", "why": f"no readable ledger at "
                           f"{GRAPH_LEDGER.name}: every descendant reads as unborn, so this run "
                           "can re-donate cells the desk has already judged"})
    ctx, record = Neighbourhood(), load_record()
    families: dict[str, Any] = {}
    picked: list[dict[str, Any]] = []
    known: set[str] = {r["root_id"] for r in roots}
    unreachable: dict[str, int] = {}
    stopped = 0
    for i, root in enumerate(roots):
        if time.monotonic() - t0 > budget_s:
            stopped = len(roots) - i
            break
        nb, skip = neighbours(root, ctx)
        row = families[root["root_id"]] = refresh(record, root, nb, skip, fates, now)
        for axis in skip:
            unreachable[axis] = unreachable.get(axis, 0) + 1
        known.update(d["cell_id"] for d in row["descendants"])
        picked.extend(pick(root, nb, known, max(0, int(max_per_root))))
    rows = rows_for(picked)

    for root_id, row in record.get("families", {}).items():
        families.setdefault(root_id, row)
    order = sorted(families.values(), key=lambda r: str(r.get("seen_at") or ""), reverse=True)
    record = {"at": now, "rule": RULE, "families": {r["root_id"]: r for r in order[:MAX_RECORDS]}}
    if stopped:
        unmeasured.append({"what": "roots not walked", "n": stopped, "why": f"the {budget_s:g}s "
                           f"budget ran out after {len(roots) - stopped} of {len(roots)} roots; "
                           "the ranking is LIVE first, so what was skipped is the weakest"})
    unmeasured += [{"what": f"axis {axis}", "n": n, "why": f"unreachable for {n} root(s); the "
                    "reason is on each root's `axes_unreachable` and the axis is NOT counted as "
                    "covered"} for axis, n in sorted(unreachable.items())]
    if ctx.unpriced:
        unmeasured.append({"what": "instruments with no H1 bars to correlate",
                           "n": len(ctx.unpriced), "symbols": sorted(ctx.unpriced)[:12],
                           "why": "their neighbours are ranked alphabetically, not by distance"})
    walked = [r for r in families.values() if str(r.get("seen_at")) == now]
    cov = [r["coverage_overall"] for r in walked if r["coverage_overall"] is not None]
    by_axis = {a: {"possible": sum(r["coverage"][a]["possible"] for r in walked),
                   "known": sum(r["coverage"][a]["tested"] for r in walked),
                   "certified": sum(1 for r in walked for d in r["descendants"]
                                    if d["axis"] == a and d["fate"] == hg.CERTIFIED),
                   "donated": sum(1 for s in picked if s["axis"] == a)}
               for a in DESCENDANT_AXES}
    report = {
        "at": now, "n_roots": len(walked), "n_roots_found": len(roots),
        "n_descendants_known": sum(len(r["descendants"]) for r in walked),
        "n_donated": len(rows), "by_axis": by_axis,
        "coverage_median": round(float(np.median(cov)), 4) if cov else None,
        "roots": [{"root_id": r["root_id"], "symbol": r["symbol"], "family": r["family"],
                   "lane": r["lane"], "forward_n": r["forward_n"],
                   "n_descendants": len(r["descendants"]),
                   "n_certified_descendants": sum(1 for d in r["descendants"]
                                                  if d["fate"] == hg.CERTIFIED),
                   "coverage": r["coverage"], "coverage_overall": r["coverage_overall"]}
                  for r in sorted(walked, key=lambda r: (-LANE_RANK.get(r["lane"], 0),
                                                         -int(r["forward_n"]), r["root_id"]))],
        "inputs": note, "budget_s": budget_s, "budget_stopped": bool(stopped),
        "seconds": round(time.monotonic() - t0, 2), "unmeasured": unmeasured, "rule": RULE}
    return report, record, rows


def _write(path: Path, doc: dict[str, Any]) -> None:
    """Atomic, and it survives the read-only destination that broke the frontier fix on Windows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:
        os.chmod(path, 0o644)
        os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="print; write nothing, donate nothing")
    ap.add_argument("--max-per-root", type=int, default=MAX_PER_ROOT,
                    help=f"new descendants one root may donate per run (default {MAX_PER_ROOT})")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    a = ap.parse_args(argv)
    rep, record, rows = build(max_per_root=a.max_per_root, budget_s=a.budget_s)
    if not a.dry_run and rows:
        from research.proposer_common import donate, donation_counts
        donate(SEAT, [dict(r) for r in rows], tests_run=rep["n_roots"])
        rep["donation"] = donation_counts()
        rep["n_donated"] = int(rep["donation"].get("donated") or 0)
        record_donations(record, rows, rep["at"])
    print(f"DESCENDANTS {rep['at']}  roots={rep['n_roots']}/{rep['n_roots_found']} "
          f"known={rep['n_descendants_known']} donated={rep['n_donated']} "
          f"coverage_median={rep['coverage_median']} {rep['seconds']}s")
    print("  by axis  " + "  ".join(f"{x}={rep['by_axis'][x]['known']}/"
                                    f"{rep['by_axis'][x]['possible']}"
                                    f"(+{rep['by_axis'][x]['donated']})" for x in DESCENDANT_AXES))
    for r in rep["roots"][:6]:
        print(f"  {r['lane']:<8} {r['symbol']:<10} {r['family']:<24} n={r['n_descendants']:<3} "
              f"certified={r['n_certified_descendants']} cover={r['coverage_overall']}")
    for u in rep["unmeasured"][:5]:
        print(f"  UNMEASURED {u['what']}: {str(u['why'])[:88]}")
    if a.dry_run:
        print("  --dry-run: nothing written, nothing donated")
        return 0
    _write(OUT, rep)
    _write(RECORD, record)
    print(f"-> {OUT}  |  {RECORD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
