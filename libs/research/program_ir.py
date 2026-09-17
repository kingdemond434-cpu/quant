"""A restricted PROGRAM algebra: candidates that branch, remember, and watch a clock.

WHY THIS EXISTS (ledger item D4, principal 2026-09-16)

`libs/research_os/dsl.py` already refuses to be an interpreter, and that refusal is the reason
this module exists rather than a reason it does not: the desk may search PROGRAMS, but it may
never execute model-written source on the box that holds the live terminal. So the DSL's idea is
extended here, not duplicated -- a JSON tree, an operator allowlist, validation before any data
is touched, evaluation by walking the tree into vetted pandas calls. There is no eval, no exec,
no attribute access, no import and no user-supplied callable anywhere in this path either.

WHAT IS NEW, and it is exactly what D4 measured as missing. `alpha_grammar` and `research_os.dsl`
both search a typed EXPRESSION: one formula evaluated identically on every bar. An expression
cannot say "while we are inside the Asia range do nothing; once it breaks, ride it until the
London close", cannot count the bars to the next month-end fixing, cannot widen its own lookback
when volatility rises, and cannot hold a threshold that re-estimates itself -- control flow,
state, an event clock, a dynamic lookback, an adaptive threshold. This IR adds them as NODES, so
the search space grows without the executor growing a way to run arbitrary code.

THE NODES ARE THE SECURITY BOUNDARY, exactly as `dsl.OPS` is: eleven frozen dataclasses with
typed fields, and anything else refused by name. A program is JSON in and JSON out, so a program
IS its recipe and `fingerprint` hashes two spellings of one hypothesis the same.

LOOK-AHEAD IS STRUCTURALLY IMPOSSIBLE. Every rolling window is trailing (pandas `rolling` at bar
i spans i-w+1..i), the state machine is a forward scan that sees each bar once, the cross-asset
reference is reindex-then-forward-fill (the other instrument's last KNOWN bar), and the event
clock is measured in ELAPSED TIME against a calendar published in advance rather than in bar
positions -- which is what makes "bars to the next event" point-in-time rather than a peek at the
end of the sample. The property is asserted, not asserted-about: `tests/research/
test_program_ir.py` re-evaluates every node on a truncated frame and on a frame whose FUTURE bars
were replaced, and requires the past outputs to be identical.

THE MONEY PATH NEVER SEES A TREE. `compile_program` returns a callable producing the desk's own
`mt5desk.engine.Signal` objects -- the contract every registered family produces -- so a program
reaching the forward engine is indistinguishable from a family, and one that cannot be compiled
reaches nothing at all.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
#: The forced-flow calendar the EventClock node reads. Tolerant: an unreadable or absent file is
#: UNMEASURED (every clock series is NaN), never a substituted calendar.
CALENDAR_PATH = DESK / "data" / "forced_flow_calendar.json"

#: Terminals a Series node may name. `hour` and `dow` are the bar's own BROKER stamp (Fusion runs
#: UTC+3, and the bars are on that clock -- see `dsl.SESSIONS`), which is how a program says
#: "inside the Asia window" without a session operator. `tr` is the true range and `atr` its
#: 14-bar mean, the desk's `families._atr` default -- imported, never re-spelled.
FIELDS: tuple[str, ...] = ("open", "high", "low", "close", "ret", "range", "body", "tr", "atr",
                           "typical", "activity", "spread", "hour", "dow")
ROLLING_OPS: tuple[str, ...] = ("mean", "std", "max", "min", "sum", "zscore", "rank")
BINARY_OPS: tuple[str, ...] = ("add", "sub", "mul", "div", "min2", "max2")
COMPARE_OPS: tuple[str, ...] = ("gt", "ge", "lt", "le")
CLOCK_MODES: tuple[str, ...] = ("since", "to")
#: The kinds `forced_flow_calendar.json` publishes. An allowlist for the same reason `dsl.OPS` is
#: one: adding a kind is a reviewable act, and a typo is refused by name instead of silently
#: producing an all-NaN clock that reads like a mechanism with no signal.
CALENDAR_KINDS: tuple[str, ...] = ("month_end", "quarter_end", "index_rebalance", "futures_roll",
                                   "option_expiry", "bond_auction", "central_bank", "fixing",
                                   "inventory", "usda", "holiday_liquidity")

MAX_DEPTH = 10
MAX_NODES = 80
MIN_WINDOW = 2
MAX_WINDOW = 1000
MAX_STATES = 6
MAX_TRANSITIONS = 4
MAX_SLOTS = 12
#: Execution slots every compiled program carries whether or not its logic mentions them. They
#: are RESERVED: a tree may not declare a Slot by these names, because two meanings for one name
#: is how an optimiser ends up tuning a stop it thinks is a lookback.
RESERVED = ("stop_atr", "rr", "ttl_bars", "atr_n")


class ProgramError(ValueError):
    """A tree this module refuses, with the reason a reviewer needs."""


# --------------------------------------------------------------------------- the node algebra
@dataclass(frozen=True)
class Const:
    """A scalar, broadcast over the bar index."""
    value: float


@dataclass(frozen=True)
class Series:
    """One terminal of the primary instrument's bars. `field` must be in `FIELDS`."""
    field: str


@dataclass(frozen=True)
class Slot:
    """A numeric the optimiser tunes, bounded by construction.

    A Slot evaluates to whatever value is bound for its name (clamped into [lo, hi]) and to
    `default` when nothing is bound -- so a program is runnable before it is ever tuned, and a
    tuning run can never push a window past `MAX_WINDOW` by handing in a larger number.
    """
    name: str
    lo: float
    hi: float
    default: float


@dataclass(frozen=True)
class Rolling:
    """A trailing statistic. `window` is a Slot (a DYNAMIC lookback) or a fixed int.

    `lag` ENDS the window that many bars ago, and it is not a convenience. `close > max(high, w)`
    is FALSE ON EVERY BAR -- the window contains this bar's own high, which is never below its
    close -- so a breakout written without it is a rule that cannot fire, and a search would read
    the resulting silence as "no edge here" rather than as "this question was never asked".
    """
    op: str
    child: Node
    window: Slot | int
    lag: Slot | int = 0


@dataclass(frozen=True)
class Binary:
    """Arithmetic on two series."""
    op: str
    left: Node
    right: Node


@dataclass(frozen=True)
class Compare:
    """A predicate as 1.0 / 0.0, so a condition is a series like everything else."""
    op: str
    left: Node
    right: Node


@dataclass(frozen=True)
class Cond:
    """CONTROL FLOW: `when` > 0 takes `then`, otherwise `otherwise`. Bar by bar, no lookahead."""
    when: Node
    then: Node
    otherwise: Node


@dataclass(frozen=True)
class Transition:
    """Leave for state `to` on the first bar `when` holds. Order inside a state is priority."""
    to: str
    when: Compare


@dataclass(frozen=True)
class StateDef:
    name: str
    value: int
    transitions: tuple[Transition, ...] = ()


@dataclass(frozen=True)
class State:
    """A STATE MACHINE, emitting the current state's `value` as a series.

    `states[0]` is the initial state. The emitted value at bar i is the state AFTER that bar's
    transitions have been tested, so it uses bar i and no later one. Encode a short as a NEGATIVE
    state value: `compile_program` reads the root's SIGN as the direction.
    """
    states: tuple[StateDef, ...]


@dataclass(frozen=True)
class EventClock:
    """Bars since the last / to the next calendar event of `kind`.

    MEASURED IN ELAPSED TIME divided by the frame's own bar span, not in bar positions. That is
    what makes "to the next event" point-in-time: the calendar is published in advance, so the
    distance to a scheduled fixing is knowable at the bar, while a bar-position count would need
    to know how many bars the market has yet to print. Weekends therefore count as bars, because
    the forced actor's deadline does not pause for them.
    """
    kind: str
    mode: str = "since"


@dataclass(frozen=True)
class Adaptive:
    """An ADAPTIVE THRESHOLD: the trailing `q`-quantile of `child` over `window`.

    A fixed threshold is a claim about a level; this is a claim about a POSITION in the recent
    distribution, which is the same claim re-estimated as the instrument's regime moves.
    """
    child: Node
    window: Slot | int
    q: Slot | float = 0.8


@dataclass(frozen=True)
class CrossRef:
    """Another instrument's field, supplied by the caller and joined causally.

    Reindexed onto the primary's bars and forward-filled: the reference's last KNOWN value. A
    symbol the caller did not supply evaluates to NaN -- UNMEASURED, never a substituted peer.
    """
    symbol: str
    field: str


Node = (Const | Series | Slot | Rolling | Binary | Compare | Cond | State | EventClock
        | Adaptive | CrossRef)

_NODE_NAMES: dict[type, str] = {
    Const: "const", Series: "series", Slot: "slot", Rolling: "rolling", Binary: "binary",
    Compare: "compare", Cond: "cond", State: "state", EventClock: "event_clock",
    Adaptive: "adaptive", CrossRef: "cross_ref",
}


@dataclass
class Extras:
    """Everything evaluation may touch beyond the primary bars. Nothing else is reachable."""
    slots: Mapping[str, float] = field(default_factory=dict)
    cross: Mapping[str, pd.DataFrame] = field(default_factory=dict)
    calendar: Sequence[Mapping[str, Any]] = ()
    symbol: str = ""


# --------------------------------------------------------------------------- JSON codec
def _win_json(w: Slot | int | float) -> Any:
    return to_json(w) if isinstance(w, Slot) else w


def to_json(tree: Node) -> dict[str, Any]:
    """The tree as plain JSON. Canonical: field order is this function's, not the caller's."""
    name = _NODE_NAMES.get(type(tree))
    if name is None:
        raise ProgramError(f"{type(tree).__name__} is not a program node")
    if isinstance(tree, Const):
        return {"node": name, "value": float(tree.value)}
    if isinstance(tree, Series):
        return {"node": name, "field": tree.field}
    if isinstance(tree, Slot):
        return {"node": name, "name": tree.name, "lo": float(tree.lo), "hi": float(tree.hi),
                "default": float(tree.default)}
    if isinstance(tree, Rolling):
        return {"node": name, "op": tree.op, "child": to_json(tree.child),
                "window": _win_json(tree.window), "lag": _win_json(tree.lag)}
    if isinstance(tree, Binary | Compare):
        return {"node": name, "op": tree.op, "left": to_json(tree.left),
                "right": to_json(tree.right)}
    if isinstance(tree, Cond):
        return {"node": name, "when": to_json(tree.when), "then": to_json(tree.then),
                "otherwise": to_json(tree.otherwise)}
    if isinstance(tree, State):
        return {"node": name, "states": [
            {"name": s.name, "value": int(s.value),
             "transitions": [{"to": t.to, "when": to_json(t.when)} for t in s.transitions]}
            for s in tree.states]}
    if isinstance(tree, EventClock):
        return {"node": name, "kind": tree.kind, "mode": tree.mode}
    if isinstance(tree, Adaptive):
        return {"node": name, "child": to_json(tree.child), "window": _win_json(tree.window),
                "q": _win_json(tree.q)}
    return {"node": name, "symbol": tree.symbol, "field": tree.field}


def _win_from(obj: Any) -> Slot | int:
    if isinstance(obj, Mapping):
        got = from_json(obj)
        if not isinstance(got, Slot):
            raise ProgramError("a window may only be a Slot or an int")
        return got
    if isinstance(obj, bool) or not isinstance(obj, (int, float)):
        raise ProgramError(f"window {obj!r} is not numeric")
    return int(obj)


def from_json(obj: Any) -> Node:
    """Rebuild a tree from JSON. An unknown node name is refused, never approximated."""
    if not isinstance(obj, Mapping):
        raise ProgramError(f"a node must be an object, got {type(obj).__name__}")
    kind = obj.get("node")
    if kind == "const":
        return Const(float(obj["value"]))
    if kind == "series":
        return Series(str(obj["field"]))
    if kind == "slot":
        return Slot(str(obj["name"]), float(obj["lo"]), float(obj["hi"]), float(obj["default"]))
    if kind == "rolling":
        return Rolling(str(obj["op"]), from_json(obj["child"]), _win_from(obj["window"]),
                       _win_from(obj.get("lag", 0)) if obj.get("lag") else 0)
    if kind in ("binary", "compare"):
        cls = Binary if kind == "binary" else Compare
        return cls(str(obj["op"]), from_json(obj["left"]), from_json(obj["right"]))
    if kind == "cond":
        return Cond(from_json(obj["when"]), from_json(obj["then"]), from_json(obj["otherwise"]))
    if kind == "state":
        states: list[StateDef] = []
        for s in obj["states"]:
            trs: list[Transition] = []
            for t in s.get("transitions", ()):
                when = from_json(t["when"])
                if not isinstance(when, Compare):
                    raise ProgramError("a transition fires on a Compare and nothing else")
                trs.append(Transition(str(t["to"]), when))
            states.append(StateDef(str(s["name"]), int(s["value"]), tuple(trs)))
        return State(tuple(states))
    if kind == "event_clock":
        return EventClock(str(obj["kind"]), str(obj.get("mode", "since")))
    if kind == "adaptive":
        q = obj.get("q", 0.8)
        qq: Slot | float = _win_from(q) if isinstance(q, Mapping) else float(q)
        return Adaptive(from_json(obj["child"]), _win_from(obj["window"]), qq)
    if kind == "cross_ref":
        return CrossRef(str(obj["symbol"]), str(obj["field"]))
    raise ProgramError(f"unknown node {kind!r}; the allowlist is {sorted(_NODE_NAMES.values())}")


def fingerprint(tree: Node) -> str:
    """A canonical hash of the LOGIC. Two trees that hash the same are one hypothesis."""
    blob = json.dumps(to_json(tree), sort_keys=True, separators=(",", ":"))
    return hashlib.blake2b(blob.encode("utf-8"), digest_size=8).hexdigest()


# --------------------------------------------------------------------------- structure
def _children(n: Node) -> tuple[Node, ...]:
    """The REPLACEABLE structural children -- what a mutation may swap out."""
    if isinstance(n, Rolling | Adaptive):
        return (n.child,)
    if isinstance(n, Binary | Compare):
        return (n.left, n.right)
    if isinstance(n, Cond):
        return (n.when, n.then, n.otherwise)
    if isinstance(n, State):
        return tuple(t.when for s in n.states for t in s.transitions)
    return ()


def _rebuild(n: Node, kids: Sequence[Node]) -> Node:
    if isinstance(n, Rolling | Adaptive):
        return replace(n, child=kids[0])
    if isinstance(n, Binary | Compare):
        return replace(n, left=kids[0], right=kids[1])
    if isinstance(n, Cond):
        return replace(n, when=kids[0], then=kids[1], otherwise=kids[2])
    if isinstance(n, State):
        it = iter(kids)
        out: list[StateDef] = []
        for s in n.states:
            trs = tuple(replace(t, when=k) if isinstance(k := next(it), Compare) else t
                        for t in s.transitions)
            out.append(replace(s, transitions=trs))
        return replace(n, states=tuple(out))
    return n


def walk(tree: Node) -> Iterator[Node]:
    """Every node, including the Slots hiding inside windows and quantiles."""
    yield tree
    for k in _children(tree):
        yield from walk(k)
    if isinstance(tree, Rolling | Adaptive) and isinstance(tree.window, Slot):
        yield tree.window
    if isinstance(tree, Rolling) and isinstance(tree.lag, Slot):
        yield tree.lag
    if isinstance(tree, Adaptive) and isinstance(tree.q, Slot):
        yield tree.q


def size(tree: Node) -> int:
    return sum(1 for _ in walk(tree))


def depth(tree: Node) -> int:
    kids = _children(tree)
    return 1 + (max(depth(k) for k in kids) if kids else 0)


def slots(tree: Node) -> list[Slot]:
    """The tuneable numerics of this tree, deduped by name. Execution slots are not here."""
    out: dict[str, Slot] = {}
    for n in walk(tree):
        if isinstance(n, Slot):
            out.setdefault(n.name, n)
    return [out[k] for k in sorted(out)]


def exec_slots() -> list[Slot]:
    """The four slots every compiled program carries: how it stops, targets, times out, sizes."""
    return [Slot("stop_atr", 0.4, 3.0, 1.2), Slot("rr", 0.8, 4.0, 1.5),
            Slot("ttl_bars", 2.0, 72.0, 8.0), Slot("atr_n", 7.0, 48.0, 14.0)]


# --------------------------------------------------------------------------- validation
def validate(tree: Any) -> list[str]:
    """Every reason this tree is not a program. Empty means it is one.

    Runs BEFORE any data is touched, exactly as `dsl.validate` does, and reports ALL the reasons
    rather than the first -- a generator that gets one refusal per attempt learns one thing per
    attempt.
    """
    errs: list[str] = []
    seen: dict[str, Slot] = {}
    _check(tree, 0, errs, seen)
    if len(seen) > MAX_SLOTS:
        errs.append(f"{len(seen)} slots; the cap is {MAX_SLOTS} -- a wider box is a longer search")
    try:
        if size(tree) > MAX_NODES:
            errs.append(f"tree larger than {MAX_NODES} nodes")
        if depth(tree) > MAX_DEPTH:
            errs.append(f"tree deeper than {MAX_DEPTH}; complexity is a redundancy risk")
    except (AttributeError, TypeError, RecursionError):
        pass
    return errs


def _check_window(w: Any, where: str, errs: list[str], seen: dict[str, Slot]) -> None:
    if isinstance(w, Slot):
        _check(w, 0, errs, seen)
        if w.lo < MIN_WINDOW or w.hi > MAX_WINDOW:
            errs.append(f"{where} slot {w.name} spans [{w.lo}, {w.hi}]; windows live in "
                        f"[{MIN_WINDOW}, {MAX_WINDOW}]")
        return
    if isinstance(w, bool) or not isinstance(w, int):
        errs.append(f"{where} must be a Slot or an int, got {type(w).__name__}")
        return
    if not MIN_WINDOW <= w <= MAX_WINDOW:
        errs.append(f"{where} {w} is outside [{MIN_WINDOW}, {MAX_WINDOW}]")


def _check(n: Any, d: int, errs: list[str], seen: dict[str, Slot]) -> None:
    if type(n) not in _NODE_NAMES:
        errs.append(f"unknown node {type(n).__name__}; the allowlist is "
                    f"{sorted(_NODE_NAMES.values())}")
        return
    if d > MAX_DEPTH:
        errs.append(f"tree deeper than {MAX_DEPTH}")
        return
    if isinstance(n, Const) and not np.isfinite(n.value):
        errs.append("a Const must be finite")
    elif isinstance(n, Series) and n.field not in FIELDS:
        errs.append(f"unknown field {n.field!r}; the terminals are {list(FIELDS)}")
    elif isinstance(n, CrossRef) and n.field not in FIELDS:
        errs.append(f"cross reference to unknown field {n.field!r}")
    elif isinstance(n, Slot):
        if n.name in RESERVED:
            errs.append(f"slot {n.name!r} is a RESERVED execution slot; a tree may not redefine it")
        if not (n.lo <= n.default <= n.hi) or not np.isfinite([n.lo, n.hi, n.default]).all():
            errs.append(f"slot {n.name}: default {n.default} outside [{n.lo}, {n.hi}]")
        prior = seen.get(n.name)
        if prior is not None and prior != n:
            errs.append(f"slot {n.name} declared twice with different bounds")
        seen.setdefault(n.name, n)
    elif isinstance(n, Rolling):
        if n.op not in ROLLING_OPS:
            errs.append(f"unknown rolling op {n.op!r}; the allowlist is {list(ROLLING_OPS)}")
        _check_window(n.window, "Rolling.window", errs, seen)
        lag = n.lag
        if isinstance(lag, Slot):
            _check(lag, d + 1, errs, seen)
            if lag.lo < 0 or lag.hi > MAX_WINDOW:
                errs.append(f"Rolling.lag slot {lag.name} must stay in [0, {MAX_WINDOW}]")
        elif isinstance(lag, bool) or not isinstance(lag, int) or not 0 <= lag <= MAX_WINDOW:
            errs.append(f"Rolling.lag {lag!r} must be an int in [0, {MAX_WINDOW}]")
    elif isinstance(n, Binary) and n.op not in BINARY_OPS:
        errs.append(f"unknown binary op {n.op!r}; the allowlist is {list(BINARY_OPS)}")
    elif isinstance(n, Compare) and n.op not in COMPARE_OPS:
        errs.append(f"unknown compare op {n.op!r}; the allowlist is {list(COMPARE_OPS)}")
    elif isinstance(n, EventClock):
        if n.kind not in CALENDAR_KINDS:
            errs.append(f"unknown calendar kind {n.kind!r}; the allowlist is "
                        f"{list(CALENDAR_KINDS)}")
        if n.mode not in CLOCK_MODES:
            errs.append(f"unknown clock mode {n.mode!r}; use one of {list(CLOCK_MODES)}")
    elif isinstance(n, Adaptive):
        _check_window(n.window, "Adaptive.window", errs, seen)
        if isinstance(n.q, Slot):
            _check(n.q, d + 1, errs, seen)
            if not (n.q.lo > 0.0 and n.q.hi < 1.0):
                errs.append(f"quantile slot {n.q.name} must stay strictly inside (0, 1)")
        elif not 0.0 < float(n.q) < 1.0:
            errs.append(f"quantile {n.q} must be strictly inside (0, 1)")
    elif isinstance(n, State):
        names = [s.name for s in n.states]
        if not 2 <= len(n.states) <= MAX_STATES:
            errs.append(f"a state machine has 2..{MAX_STATES} states, got {len(n.states)}")
        if len(set(names)) != len(names):
            errs.append("two states share a name")
        for s in n.states:
            if len(s.transitions) > MAX_TRANSITIONS:
                errs.append(f"state {s.name} has more than {MAX_TRANSITIONS} transitions")
            for t in s.transitions:
                if t.to not in names:
                    errs.append(f"state {s.name} transitions to unknown state {t.to!r}")
                if not isinstance(t.when, Compare):
                    errs.append(f"state {s.name}: a transition fires on a Compare only")
    for k in _children(n):
        _check(k, d + 1, errs, seen)


# --------------------------------------------------------------------------- evaluation
_DESK: Any = None


def _desk() -> Any:
    """The desk package, for the ONE spelling of ATR and the ONE Signal contract."""
    global _DESK
    if _DESK is None:
        # APPENDED, never inserted. `desks/mt5` carries top-level `research` and `scripts`
        # packages whose names also exist at the repository root, and putting it first would
        # silently re-point every OTHER importer in the process at the desk's copies.
        if str(DESK) not in sys.path:
            sys.path.append(str(DESK))
        try:
            from mt5desk import families
        except Exception as exc:                                 # pragma: no cover - install
            raise ProgramError(f"mt5desk is unreachable ({type(exc).__name__}: {exc}); a program "
                               "may not carry a second spelling of the desk's ATR or Signal") \
                from exc
        _DESK = families
    return _DESK


def _signal() -> Any:
    """The desk's OWN Signal class. One contract; a local re-spelling would diverge silently."""
    _desk()
    from mt5desk.engine import Signal
    return Signal


def _nan(idx: pd.Index) -> pd.Series:
    return pd.Series(np.nan, index=idx, dtype=float)


def _value(x: Slot | int | float, ex: Extras) -> float:
    if isinstance(x, Slot):
        v = float(ex.slots.get(x.name, x.default))
        return float(min(max(v, x.lo), x.hi))
    return float(x)


def _window(x: Slot | int | float, ex: Extras) -> int:
    return int(min(max(round(_value(x, ex)), MIN_WINDOW), MAX_WINDOW))


def _terminal(bars: pd.DataFrame, name: str) -> pd.Series:
    idx = bars.index
    if name in ("open", "high", "low", "close"):
        return bars[name].astype(float) if name in bars.columns else _nan(idx)
    if name in ("activity", "spread"):
        col = "tick_volume" if name == "activity" else "spread"
        return bars[col].astype(float) if col in bars.columns else _nan(idx)
    if name in ("hour", "dow"):
        if not isinstance(idx, pd.DatetimeIndex):
            return _nan(idx)
        vals = idx.hour if name == "hour" else idx.dayofweek
        return pd.Series(np.asarray(vals, dtype=float), index=idx)
    if any(c not in bars.columns for c in ("open", "high", "low", "close")):
        return _nan(idx)
    h, lo, c, o = (bars["high"].astype(float), bars["low"].astype(float),
                   bars["close"].astype(float), bars["open"].astype(float))
    if name == "ret":
        with np.errstate(all="ignore"):
            return pd.Series(np.log(c.to_numpy(dtype=float)), index=idx).diff()
    if name == "range":
        return h - lo
    if name == "body":
        return c - o
    if name == "typical":
        return (h + lo + c) / 3.0
    prev = c.shift(1)
    tr = pd.concat([h - lo, (h - prev).abs(), (lo - prev).abs()], axis=1).max(axis=1)
    if name == "tr":
        return tr
    atr: pd.Series = _desk()._atr(bars, 14)
    return atr.astype(float)


def _event_clock(node: EventClock, bars: pd.DataFrame, ex: Extras) -> pd.Series:
    idx = bars.index
    if not isinstance(idx, pd.DatetimeIndex) or not len(idx):
        return _nan(idx)
    sym = str(ex.symbol or "").upper()
    times: list[pd.Timestamp] = []
    for row in ex.calendar:
        if str(row.get("kind", "")) != node.kind:
            continue
        inst = row.get("instruments")
        if sym and isinstance(inst, (list, tuple)) and inst and sym not in {
                str(i).upper() for i in inst}:
            continue
        ts = pd.to_datetime(row.get("window_start_utc") or row.get("date"), utc=True,
                            errors="coerce")
        if ts is not pd.NaT and not pd.isna(ts):
            times.append(ts)
    if not times:
        return _nan(idx)
    span = pd.Series(idx).diff().dt.total_seconds().mode()
    step = float(span.iloc[0]) if len(span) and float(span.iloc[0]) > 0 else 3600.0
    ev = np.sort(np.asarray(pd.DatetimeIndex(times).view("int64"), dtype=np.float64)) / 1e9
    now = np.asarray(idx.view("int64"), dtype=np.float64) / 1e9
    if node.mode == "since":
        pos = np.searchsorted(ev, now, side="right") - 1
        out = np.where(pos >= 0, (now - ev[np.clip(pos, 0, ev.size - 1)]) / step, np.nan)
    else:
        pos = np.searchsorted(ev, now, side="left")
        out = np.where(pos < ev.size, (ev[np.clip(pos, 0, ev.size - 1)] - now) / step, np.nan)
    return pd.Series(out, index=idx, dtype=float)


def _state(node: State, bars: pd.DataFrame, ex: Extras) -> pd.Series:
    idx = bars.index
    n = len(idx)
    order = {s.name: i for i, s in enumerate(node.states)}
    values = np.asarray([s.value for s in node.states], dtype=float)
    masks: list[list[tuple[int, np.ndarray]]] = []
    for s in node.states:
        row: list[tuple[int, np.ndarray]] = []
        for t in s.transitions:
            m = _eval(t.when, bars, ex).to_numpy(dtype=float)
            row.append((order[t.to], np.nan_to_num(m, nan=0.0) > 0.5))
        masks.append(row)
    out = np.empty(n, dtype=float)
    cur = 0
    for i in range(n):
        for tgt, m in masks[cur]:
            if m[i]:
                cur = tgt
                break
        out[i] = values[cur]
    return pd.Series(out, index=idx, dtype=float)


def _rolling(op: str, s: pd.Series, w: int, lag: int = 0) -> pd.Series:
    if lag:
        s = s.shift(lag)
    r = s.rolling(w)
    if op == "zscore":
        sd = r.std()
        return (s - r.mean()) / sd.where(sd.abs() > 1e-12)
    if op == "rank":
        return r.rank(pct=True)
    out: pd.Series = getattr(r, op)()
    return out


def _eval(n: Node, bars: pd.DataFrame, ex: Extras) -> pd.Series:
    idx = bars.index
    if isinstance(n, Const):
        return pd.Series(float(n.value), index=idx, dtype=float)
    if isinstance(n, Slot):
        return pd.Series(_value(n, ex), index=idx, dtype=float)
    if isinstance(n, Series):
        return _terminal(bars, n.field)
    if isinstance(n, CrossRef):
        other = ex.cross.get(n.symbol)
        if other is None or not len(other):
            return _nan(idx)
        s = _terminal(other, n.field)
        return s.reindex(s.index.union(idx)).ffill().reindex(idx).astype(float)
    if isinstance(n, EventClock):
        return _event_clock(n, bars, ex)
    if isinstance(n, State):
        return _state(n, bars, ex)
    if isinstance(n, Rolling):
        lag = int(min(max(round(_value(n.lag, ex)), 0), MAX_WINDOW))
        return _rolling(n.op, _eval(n.child, bars, ex), _window(n.window, ex), lag)
    if isinstance(n, Adaptive):
        q = float(min(max(_value(n.q, ex), 0.001), 0.999))
        return _eval(n.child, bars, ex).rolling(_window(n.window, ex)).quantile(q)
    if isinstance(n, Cond):
        when = _eval(n.when, bars, ex)
        return _eval(n.then, bars, ex).where(when > 0, _eval(n.otherwise, bars, ex))
    a, b = _eval(n.left, bars, ex), _eval(n.right, bars, ex)
    if isinstance(n, Compare):
        cmps: dict[str, pd.Series] = {"gt": a > b, "ge": a >= b, "lt": a < b, "le": a <= b}
        return cmps[n.op].astype(float).where(a.notna() & b.notna())
    if n.op == "add":
        return a + b
    if n.op == "sub":
        return a - b
    if n.op == "mul":
        return a * b
    if n.op == "div":
        return a / b.where(b.abs() > 1e-12)
    frame = pd.concat([a, b], axis=1)
    return frame.max(axis=1) if n.op == "max2" else frame.min(axis=1)


def evaluate(tree: Node, bars: pd.DataFrame, extras: Extras | None = None) -> pd.Series:
    """Validate, then walk. Only the operations named above are ever called.

    The result is a float series on `bars.index`; NaN means "not computable here", which every
    consumer reads as no signal rather than as a zero.
    """
    errs = validate(tree)
    if errs:
        raise ProgramError("; ".join(errs))
    out = _eval(tree, bars, extras if extras is not None else Extras())
    return out.astype(float).replace([np.inf, -np.inf], np.nan)


def load_calendar(path: Path | None = None) -> list[dict[str, Any]]:
    """The forced-flow calendar's events, or [] with nothing claimed (L1.28a)."""
    try:
        raw = json.loads((path or CALENDAR_PATH).read_text("utf-8"))
    except (OSError, ValueError):
        return []
    events = raw.get("events") if isinstance(raw, dict) else raw
    return [e for e in events if isinstance(e, dict)] if isinstance(events, list) else []


# --------------------------------------------------------------------------- compilation
def compile_program(tree: Node, extras: Extras | None = None, tag: str = "program",
                    ) -> Callable[..., list[Any]]:
    """The tree as a family: `fn(bars, side=1, **slot_values) -> list[Signal]`.

    ENTRY IS THE NEXT OPEN, as the engine fills it, and only on an EDGE -- the bar where the
    program's sign changes into +1 or -1. A state machine that stays long for 300 bars is one
    trade, not 300 signals; emitting a signal per bar would hand the screen 300 overlapping
    copies of one decision and call the last 299 of them independent evidence.

    `side` is the POLARITY the program is traded at, exactly as `family_generic`'s DIRECTION axis
    is: +1 takes the program's own sign, -1 takes the opposite. Stops and targets are ATR
    multiples from the reserved execution slots, so the same threshold means the same thing on
    gold and on EURCHF.
    """
    errs = validate(tree)
    if errs:
        raise ProgramError("; ".join(errs))
    ex_base = extras if extras is not None else Extras()
    defaults = {s.name: s.default for s in exec_slots()}
    bounds = {s.name: (s.lo, s.hi) for s in exec_slots()}
    fp = fingerprint(tree)

    signal_cls = _signal()

    def run(bars: pd.DataFrame, side: int = 1, **slot_values: float) -> list[Any]:
        if bars is None or not len(bars) or "close" not in bars.columns:
            return []
        ex = Extras(slots={**dict(ex_base.slots), **{k: float(v) for k, v in slot_values.items()}},
                    cross=ex_base.cross, calendar=ex_base.calendar, symbol=ex_base.symbol)
        vals: dict[str, float] = {}
        for k, dflt in defaults.items():
            lo, hi = bounds[k]
            vals[k] = float(min(max(float(ex.slots.get(k, dflt)), lo), hi))
        raw = evaluate(tree, bars, ex).to_numpy(dtype=float)
        sgn = np.clip(np.sign(np.nan_to_num(raw, nan=0.0)), -1.0, 1.0)
        atr = _desk()._atr(bars, round(vals["atr_n"])).to_numpy(dtype=float)
        close = bars["close"].astype(float).to_numpy(dtype=float)
        idx = bars.index
        ttl = round(vals["ttl_bars"])
        out: list[Any] = []
        for i in range(1, len(idx) - 1):
            d = sgn[i]
            if d == 0.0 or d == sgn[i - 1]:
                continue
            a, px = atr[i], close[i]
            if not (np.isfinite(a) and a > 0 and np.isfinite(px)):
                continue
            s = int(d) * int(np.sign(side) or 1)
            stop_d = vals["stop_atr"] * a
            out.append(signal_cls(time=idx[i], side=s, stop=px - s * stop_d,
                              target=px + s * stop_d * vals["rr"], ttl_bars=ttl,
                              tag=f"{tag}:{fp}", trigger=None, wait_bars=1))
        return out

    return run


# --------------------------------------------------------------------------- description
def _win_str(w: Slot | int | float) -> str:
    return f"{w.name}[{w.lo:g}..{w.hi:g}]" if isinstance(w, Slot) else f"{w:g}"


_CMP = {"gt": ">", "ge": ">=", "lt": "<", "le": "<="}
_BIN = {"add": "+", "sub": "-", "mul": "*", "div": "/"}


def describe(tree: Node) -> str:
    """The rule in one line of English-ish arithmetic. What a reviewer reads instead of JSON."""
    if isinstance(tree, Const):
        return f"{tree.value:g}"
    if isinstance(tree, Series):
        return tree.field
    if isinstance(tree, Slot):
        return _win_str(tree)
    if isinstance(tree, CrossRef):
        return f"{tree.symbol}.{tree.field}"
    if isinstance(tree, EventClock):
        return f"bars_{tree.mode}({tree.kind})"
    if isinstance(tree, Rolling):
        tail = "" if tree.lag == 0 else f", lag={_win_str(tree.lag)}"
        return f"{tree.op}({describe(tree.child)}, {_win_str(tree.window)}{tail})"
    if isinstance(tree, Adaptive):
        return f"quantile({describe(tree.child)}, {_win_str(tree.window)}, q={_win_str(tree.q)})"
    if isinstance(tree, Compare):
        return f"({describe(tree.left)} {_CMP[tree.op]} {describe(tree.right)})"
    if isinstance(tree, Binary):
        if tree.op in _BIN:
            return f"({describe(tree.left)} {_BIN[tree.op]} {describe(tree.right)})"
        return f"{tree.op}({describe(tree.left)}, {describe(tree.right)})"
    if isinstance(tree, Cond):
        return (f"if {describe(tree.when)} then {describe(tree.then)} "
                f"else {describe(tree.otherwise)}")
    parts = []
    for s in tree.states:
        arcs = ", ".join(f"-{describe(t.when)}-> {t.to}" for t in s.transitions) or "terminal"
        parts.append(f"{s.name}={s.value}: {arcs}")
    return "state{" + "; ".join(parts) + "}"


# --------------------------------------------------------------------------- logic revision
def _count(tree: Node) -> int:
    return 1 + sum(_count(k) for k in _children(tree))


def _map_nth(n: Node, target: int, new: Node, ctr: list[int]) -> Node:
    here = ctr[0]
    ctr[0] += 1
    if here == target:
        return new
    kids = _children(n)
    return _rebuild(n, [_map_nth(k, target, new, ctr) for k in kids]) if kids else n


def _nth(n: Node, target: int, ctr: list[int]) -> Node | None:
    here = ctr[0]
    ctr[0] += 1
    if here == target:
        return n
    for k in _children(n):
        got = _nth(k, target, ctr)
        if got is not None:
            return got
    return None


def _rand_compare(rng: np.random.Generator) -> Compare:
    f = str(rng.choice(np.asarray(["close", "ret", "range", "tr", "body"])))
    w = int(rng.choice(np.asarray([8, 12, 24, 48, 120])))
    op = str(rng.choice(np.asarray(list(COMPARE_OPS))))
    return Compare(op, Series(f), Rolling("mean", Series(f), w))


def mutate_logic(tree: Node, rng: np.random.Generator, tries: int = 12) -> Node:
    """One STRUCTURAL edit: the mechanical half of what a seat's logic revision does by hand.

    D4 asks for logic revision to be SEPARATE from numeric tuning, and this is the separation
    made concrete: nothing here moves a slot's value -- it swaps a comparison, wraps a subtree in
    a branch, turns a rule into a state machine, changes an operator or re-aims a terminal. The
    optimiser tunes; this changes what is being tuned. A mutation that does not validate is
    discarded and the original returned, so a caller never receives an unrunnable program.
    """
    n = _count(tree)
    for _ in range(max(1, tries)):
        k = int(rng.integers(0, n))
        node = _nth(tree, k, [0])
        if node is None:
            continue
        choice = str(rng.choice(np.asarray(["op", "compare", "wrap", "state", "field", "roll"])))
        new: Node | None = None
        if choice == "compare" and isinstance(node, Compare):
            new = replace(node, op=str(rng.choice(np.asarray(list(COMPARE_OPS)))))
        elif choice == "op" and isinstance(node, Binary):
            new = replace(node, op=str(rng.choice(np.asarray(list(BINARY_OPS)))))
        elif choice == "roll" and isinstance(node, Rolling):
            new = replace(node, op=str(rng.choice(np.asarray(list(ROLLING_OPS)))))
        elif choice == "field" and isinstance(node, Series):
            new = replace(node, field=str(rng.choice(np.asarray(list(FIELDS[:8])))))
        elif choice == "wrap":
            new = Cond(_rand_compare(rng), node, Const(0.0))
        elif choice == "state":
            c1, c2 = _rand_compare(rng), _rand_compare(rng)
            new = State((StateDef("flat", 0, (Transition("engaged", c1),)),
                         StateDef("engaged", 1, (Transition("flat", c2),))))
        if new is None:
            continue
        cand = _map_nth(tree, k, new, [0])
        if not validate(cand):
            return cand
    return tree
