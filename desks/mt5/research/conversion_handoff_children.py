"""conversion_handoff_children: child planning per reason: relaxed, coarser, input presence.

Split out of conversion_handoff_converter.py so each file of the organ is a size the
independent reviewer can read whole. conversion_handoff_converter re-exports every name here;
the organ's behaviour and docstring live there."""

from __future__ import annotations

import os
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from research.conversion_handoff_common import (
    BUDGET_SHARE,
    DEFECT_SAMPLES,
    DESK,
    GAPS_LISTED,
    INPUT_MISSING,
    MAX_CHILDREN_NEVER_FIRES,
    NEVER_FIRES,
    RETRY_H,
    ROUTE_COARSER,
    ROUTE_POOL,
    ROUTE_RELAXED,
    ROUTE_RESTORED,
    ROUTE_TRANSPLANT,
    SEAT,
    SHORT_HISTORY,
    TOO_RARE,
    UNIVERSE,
)
from research.conversion_handoff_routes import (
    _num,
    _policy,
    lane_allows,
    ranked_peers,
)

EXIT_PARAM = re.compile(r"^(rr|rr_mult|ttl_bars|ttl_mult|hold_bars|hold_d|stop_atr|atr_n|"
                        r"timeframe|wait_bars)$")
#: Entry params where a HIGHER value fires more often (a low quantile, an oversold level, a cap).
HIGHER_FIRES = re.compile(r"^(lo_q|oversold)$|^max_")
#: Entry params where a LOWER value fires more often (thresholds, band widths, ATR triggers,
#: an upper quantile, an overbought level, a breakout channel, any minimum).
LOWER_FIRES = re.compile(r"thresh|_atr$|^bb_k$|^vol_mult$|^overbought$|^hi_q$|^stress_q$|"
                         r"^channel$|^min_|_pct$|^z$|^k$|sigma|_mult$")
#: The loosest value a categorical entry filter can take, when the grid offers it.
LOOSE_CATEGORIES = ("any", "all", "none", "off")


def family_param_space(family: str) -> tuple[dict[str, list[Any]], dict[str, Any]]:
    """(grid, defaults) for `family` from the family registry, READ-ONLY; ({}, {}) if none."""
    grid: dict[str, list[Any]] = {}
    defaults: dict[str, Any] = {}
    try:
        from mt5desk.families import FAMILY_REGISTRY
        entry = FAMILY_REGISTRY.get(family)
        if entry:
            grid = {k: list(v) for k, v in dict(entry.get("param_grid") or {}).items()}
            defaults = dict(entry.get("defaults") or {})
    except Exception:
        pass
    if not grid:
        try:
            from mt5desk import families_cross_sectional as xs
            grid = {k: list(v) for k, v in dict(xs.PARAM_GRID.get(family) or {}).items()}
        except Exception:
            pass
    return grid, defaults


def _looser(name: str, current: Any, values: Sequence[Any]) -> list[Any]:
    """Grid values of `name` looser than `current`, nearest first; [] when none or no direction."""
    if EXIT_PARAM.search(name):
        return []
    if isinstance(current, str):
        loose = [v for v in values if v in LOOSE_CATEGORIES]
        return [loose[0]] if loose and current not in LOOSE_CATEGORIES else []
    cur = _num(current)
    if cur is None:
        return []
    nums = sorted({float(v) for v in values if _num(v) is not None})
    if HIGHER_FIRES.search(name):
        out = [v for v in nums if v > cur]
    elif LOWER_FIRES.search(name):
        out = sorted((v for v in nums if v < cur), reverse=True)
    else:
        return []
    # Keep the grid's own spelling (an int stays an int).
    spelled = {float(v): v for v in values if _num(v) is not None}
    return [spelled[v] for v in out]


def relaxed_children(params: Mapping[str, Any], grid: Mapping[str, Sequence[Any]],
                     defaults: Mapping[str, Any] | None = None,
                     max_children: int = MAX_CHILDREN_NEVER_FIRES
                     ) -> tuple[list[dict[str, Any]], str | None]:
    """Up to `max_children` relaxations, ONE param each: the first relaxable param's next grid
    step, then its loosest grid value (or the next param's step when it has only one).
    Returns ([{"param", "from", "to", "params"}], why-none)."""
    defaults = defaults or {}
    steps: list[tuple[str, Any, list[Any]]] = []
    for name in sorted(grid):
        cur = params.get(name, defaults.get(name))
        if cur is None:
            continue
        loose = _looser(name, cur, list(grid[name]))
        if loose:
            steps.append((name, cur, loose))
    if not steps:
        return [], ("the family's grid exposes no relaxable entry param "
                    f"(grid params: {sorted(grid) or 'none'}; exit-side params are never "
                    "relaxed)")
    out: list[dict[str, Any]] = []
    name, cur, loose = steps[0]
    picks = [(name, cur, loose[0])]
    if len(loose) > 1:
        picks.append((name, cur, loose[-1]))
    elif len(steps) > 1:
        picks.append((steps[1][0], steps[1][1], steps[1][2][0]))
    for name, cur, to in picks[:max_children]:
        out.append({"param": name, "from": cur, "to": to, "params": {**params, name: to}})
    return out, None


# =============================================================================================
# too_rare -> coarser_timeframe / cross_sectional_pool
# =============================================================================================

CHART_LADDER: tuple[str, ...] = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")
_PINNED: dict[str, str] | None = None


def pinned_timeframes() -> dict[str, str]:
    """The judge's per-family chart pins (`external_gauntlet._PINNED_TIMEFRAME`), read from its
    source text so the sealed module is neither imported nor edited; {} when unreadable."""
    global _PINNED
    if _PINNED is None:
        _PINNED = {}
        try:
            import ast
            text = (DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")
            m = re.search(r"^_PINNED_TIMEFRAME\s*=\s*(\{[^}]*\})", text, re.M)
            if m:
                got = ast.literal_eval(m.group(1))
                if isinstance(got, dict):
                    _PINNED = {str(k): str(v) for k, v in got.items()}
        except Exception:
            _PINNED = {}
    return _PINNED


def coarser_chart(timeframe: str, family: str = "") -> tuple[str | None, str | None]:
    """The next rung up the chart ladder, or (None, why)."""
    if family in pinned_timeframes():
        return None, f"{family} is pinned to {pinned_timeframes()[family]} by the judge"
    tf = str(timeframe or "H1").upper()
    if tf not in CHART_LADDER:
        return None, f"{tf} is not on the chart ladder {CHART_LADDER}"
    i = CHART_LADDER.index(tf)
    if i + 1 >= len(CHART_LADDER):
        return None, f"{tf} is already the coarsest chart on the ladder"
    return CHART_LADDER[i + 1], None


# =============================================================================================
# build_input_missing -> the data-gap report, and the retry
# =============================================================================================

def input_labels(row: Mapping[str, Any]) -> list[str]:
    """The inputs a parked row lacks, as stable labels (`bars:<file>`, `surface:<sym>`, ...)."""
    mi = row.get("missing_input")
    items: Any = None
    if isinstance(mi, dict):
        items = mi.get("inputs") if mi.get("inputs") is not None else (
            [mi.get("input")] if mi.get("input") else None)
    if items is None:
        items = row.get("missing")
    out: list[str] = []
    for it in items if isinstance(items, list) else ([items] if items else []):
        if isinstance(it, str) and it:
            out.append(it)
        elif isinstance(it, dict):
            kind = str(it.get("kind") or "unknown")
            what = it.get("file") or it.get("symbol") or it.get("input") or ""
            out.append(f"{kind}:{what}" if what else kind)
    return out


class InputPresence:
    """Is a labelled input present now? True / False / None (cannot say), memoised per pass.
    Bars are a stat in the universe directory; other kinds ask `build_input_probe.present`."""

    def __init__(self, universe: Path | None = None) -> None:
        self.universe = universe or UNIVERSE
        self.memo: dict[str, bool | None] = {}
        self._probe: Any = None
        self._ctx: Any = None
        self._probe_failed = False

    def __call__(self, label: str) -> bool | None:
        if label in self.memo:
            return self.memo[label]
        kind, _, rest = label.partition(":")
        got = (self.universe / rest).exists() if kind == "bars" and rest else (
            self._ask_probe(label))
        self.memo[label] = got
        return got

    def _ask_probe(self, label: str) -> bool | None:
        if self._probe_failed:
            return None
        try:
            if self._probe is None:
                try:
                    import build_input_probe as probe
                except ImportError:                               # pragma: no cover - import ctx
                    from research import build_input_probe as probe
                self._probe = probe
                self._ctx = probe._Pass()
            parsed = self._probe.parse_label(label)
            if parsed is None:
                return None
            return bool(self._probe.present(parsed, self._ctx))
        except Exception:
            self._probe_failed = True
            return None


class GapAggregate:
    """(missing input -> cells blocked, families, samples) over every unresolved
    build_input_missing row in the handoff."""

    def __init__(self) -> None:
        self.by_input: Counter[str] = Counter()
        self.families: dict[str, Counter[str]] = defaultdict(Counter)
        self.samples: dict[str, list[str]] = defaultdict(list)
        self.rows = 0

    def add(self, row: Mapping[str, Any]) -> list[str]:
        labels = input_labels(row) or ["(input not named)"]
        self.rows += 1
        for lab in labels:
            self.by_input[lab] += 1
            self.families[lab][str(row.get("family") or "?")] += 1
            if len(self.samples[lab]) < DEFECT_SAMPLES:
                self.samples[lab].append(str(row.get("cell") or ""))
        return labels

    def report(self, present: Callable[[str], bool | None], *, at: str,
               handoff: Mapping[str, Any], partial: bool) -> dict[str, Any]:
        ranked = []
        for lab, n in self.by_input.most_common(GAPS_LISTED):
            now = present(lab) if lab != "(input not named)" else None
            ranked.append({"input": lab, "kind": lab.partition(":")[0], "cells_blocked": n,
                           "present_now": now,
                           "families": dict(self.families[lab].most_common(10)),
                           "sample_cells": list(self.samples[lab])})
        return {"generated_utc": at, "schema_version": 1, "producer": SEAT,
                "handoff": dict(handoff), "partial": partial,
                "build_input_missing_rows": self.rows, "distinct_inputs": len(self.by_input),
                "ranked": ranked,
                "rule": ("a missing input is a data gap, never a hypothesis: no trial is charged "
                         "until the input exists and a real cell is minted. Rows are re-examined "
                         f"every {RETRY_H:.0f}h and convert (route input_restored) when every "
                         "input they name is present. `present_now: null` means the desk could "
                         "not say (UNMEASURED), never present.")}


# =============================================================================================
# THE PASS
# =============================================================================================

def _budget_s(requested: float, env: Mapping[str, str] | None = None) -> float:
    """BUDGET_SHARE of the smaller of --budget-s and the cycle's cap (QUANT_LEG_BUDGET_S)."""
    src = os.environ if env is None else env
    cap = requested
    try:
        leg = float(src.get("QUANT_LEG_BUDGET_S") or 0)
    except ValueError:
        leg = 0.0
    if leg > 0:
        cap = min(cap, leg)
    return max(1.0, cap) * BUDGET_SHARE


def lane_refusal(symbol: str, family: str) -> str | None:
    """Why a child on `symbol` may not be minted in `family`, or None when the lane allows it."""
    up = _policy()
    if lane_allows(symbol, family):
        return None
    if up.is_equity(symbol):
        return ("two-lane law: the parent is a share CFD and the family is not a cross-sectional "
                "class book (universe_policy.CROSS_SECTIONAL_FAMILIES)")
    return (f"{symbol} is not in the hypothesis lane (universe_policy.lane={up.lane(symbol)!r}): "
            "unclassified, event-lane or off the MT5 universe, never hunted")


ParamSpace = Callable[[str], tuple[dict[str, list[Any]], dict[str, Any]]]


def plan_children(parent: Mapping[str, Any], params: Mapping[str, Any], tf: str, *,
                  universe: Path | None, space: ParamSpace
                  ) -> tuple[list[dict[str, Any]], int, str | None]:
    """The candidate children of one parent, most preferred first, and how many may be new.

    Returns (specs, max_new, why-none); each spec is {symbol, params, tf, route, mechanism,
    detail}. The caller skips specs already charged or already in the registry."""
    reason = str(parent.get("reason") or "")
    sym = str(parent.get("symbol") or "")
    fam = str(parent.get("family") or "")
    cell = parent.get("cell")
    if reason == SHORT_HISTORY:
        peers, why = ranked_peers(sym, fam, tf, universe=universe)
        return ([{"symbol": p, "params": dict(params), "tf": tf, "route": ROUTE_TRANSPLANT,
                  "mechanism": (f"{fam} on {p}: the same rule as {cell}, transplanted to a "
                                "same-class peer whose history predates the lockbox cut"),
                  "detail": {}} for p in peers], 1, why)
    refusal = lane_refusal(sym, fam)
    if refusal:
        return [], 0, refusal
    if reason == NEVER_FIRES:
        grid, defaults = space(fam)
        kids, why = relaxed_children(params, grid, defaults)
        return ([{"symbol": sym, "params": k["params"], "tf": tf, "route": ROUTE_RELAXED,
                  "mechanism": (f"{fam} on {sym} {tf}: {cell} never fired, so its entry param "
                                f"{k['param']} is relaxed {k['from']} -> {k['to']} along the "
                                "family's own grid toward firing"),
                  "detail": {"relaxed_param": k["param"], "from": k["from"], "to": k["to"]}}
                 for k in kids], MAX_CHILDREN_NEVER_FIRES, why)
    if reason == TOO_RARE:
        specs: list[dict[str, Any]] = []
        whys: list[str] = []
        if fam in _policy().CROSS_SECTIONAL_FAMILIES:
            peers, pwhy = ranked_peers(sym, fam, tf, universe=universe, min_lead_days=None)
            specs += [{"symbol": p, "params": dict(params), "tf": tf, "route": ROUTE_POOL,
                       "mechanism": (f"{fam}: {cell} fires too rarely on {sym}; the same class "
                                     f"book is pooled onto same-class panel member {p}, whose "
                                     "longer history gives the ranking more dates"),
                       "detail": {"pooled_onto": p}} for p in peers]
            if pwhy:
                whys.append(pwhy)
        child_tf, cwhy = coarser_chart(tf, fam)
        if child_tf:
            specs.append({"symbol": sym, "params": {**params, "timeframe": child_tf},
                          "tf": child_tf, "route": ROUTE_COARSER,
                          "mechanism": (f"{fam} on {sym}: {cell} fires on too few days on {tf}; "
                                        f"the same rule one rung up the chart ladder, on "
                                        f"{child_tf} (resampled exactly from {tf} by "
                                        "conversion_maximiser.backfill_bars, or served native)"),
                          "detail": {"from_timeframe": tf, "to_timeframe": child_tf}})
        elif cwhy:
            whys.append(cwhy)
        return specs, 1, ("; ".join(whys) or None) if not specs else None
    if reason == INPUT_MISSING:
        return ([{"symbol": sym, "params": dict(params), "tf": tf, "route": ROUTE_RESTORED,
                  "mechanism": (f"{fam} on {sym} {tf}: every input {cell} lacked now exists, "
                                "so the same rule is minted as the cell it always was"),
                  "detail": {"inputs": list(parent.get("inputs") or [])}}], 1, None)
    return [], 0, f"no route for reason {reason!r}"


def round_robin(queues: Mapping[str, Sequence[dict[str, Any]]], limit: int,
                order: Sequence[str] | None = None) -> list[dict[str, Any]]:
    """One row from each family in turn until `limit`, so no family starves another."""
    fams = list(order) if order is not None else sorted(queues)
    idx = dict.fromkeys(fams, 0)
    out: list[dict[str, Any]] = []
    while len(out) < limit:
        moved = False
        for f in fams:
            q = queues.get(f) or ()
            if idx[f] < len(q):
                out.append(q[idx[f]])
                idx[f] += 1
                moved = True
                if len(out) >= limit:
                    break
        if not moved:
            break
    return out


_SLIM = ("cell", "family", "trial_family", "symbol", "timeframe", "reason", "why",
         "first_parked_utc")
