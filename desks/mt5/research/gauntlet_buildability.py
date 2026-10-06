"""Can the SEALED gauntlet actually build and judge this cell? Answered from its own code.

THE PRINCIPAL'S WORD WAS "testable" (2026-09-30), and a registered family is not the same thing.
A cell is testable only when `scripts/external_gauntlet.build_cell` -- sealed, never edited from a
producer's side -- can construct its signals: it must find the family (`families.family_<name>`
or `families_orthogonal.ORTHOGONAL_FAMILIES`, the same two lookups it makes), and every DATA
input the family needs must be one the gauntlet's build path supplies. A family whose driver,
panel, legs or surface the gauntlet never loads is called with that input `None`, returns no
signals, and is judged as though the market had said no. That is not a test of the mechanism; it
is a test of the fallback, which is the rule `breadth_sweep` already states for its own BLOCKED
families, applied here to every producer.

MEASURED 2026-09-30 by building real cells through the sealed `build_cell` on this tree's bars
(pinned by `desks/mt5/tests/test_producer_breadth`): `lead_lag` and `execution_state` had no
branch, so their driver and surface were never loaded, and `event_reaction`'s branch handed a bare
DatetimeIndex with no `symbol`, so all three built ZERO signals. Sealed pass 2 (76895fedc,
2026-10-01) re-signed the gauntlet with a `lead_lag` and an `execution_state` branch and an
`event_reaction` branch that passes `events_for_symbol(events, sym)` with `symbol=sym`. The first
two are picked up from the source; the declared defect is retired. The tests now pin the
re-signed truth, so a gauntlet that loses a branch fails them the same way.

WHAT IS DERIVED AND WHAT IS DECLARED. The set of families whose inputs the gauntlet loads is READ
from `build_cell`'s own source (its `family == "x"` / `family in {...}` branches), so a re-signed
gauntlet that adds a branch is picked up without editing this file. A branch that exists but
hands the wrong SHAPE cannot be derived from text, so those are DECLARED in
`SEALED_INPUT_DEFECTS`, each with its measurement and each pinned by a test.
"""
from __future__ import annotations

import inspect
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
for _p in (str(BASE), str(BASE.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SEALED_GAUNTLET = BASE / "scripts" / "external_gauntlet.py"

BUILDABLE = "BUILDABLE"
BANNED = "BANNED"
NO_IMPLEMENTATION = "NO_IMPLEMENTATION"
INPUT_NOT_SUPPLIED = "INPUT_NOT_SUPPLIED"
SEALED_INPUT_DEFECT = "SEALED_INPUT_DEFECT"
TIMEFRAME_REFUSED = "TIMEFRAME_REFUSED"
MISSING_PARAMS = "MISSING_PARAMS"
UNMEASURED = "UNMEASURED"

#: Keyword arguments that are DATA, not parameters: a cell cannot carry them as JSON, so unless
#: the gauntlet's build path loads them the family is called with `None` (or raises on a required
#: one). Everything else a family takes is a parameter a cell can carry by value. `formula`'s
#: `drivers` is deliberately absent: it is OPTIONAL (an expression over the instrument's own bars
#: needs none), and `ensemble`'s `members` is a JSON list a cell carries -- its `_runner` is not.
DATA_INPUT_ARGS: frozenset[str] = frozenset({
    "driver", "peer", "peers", "factors", "cot", "events", "macro", "fx",
    "spread_series", "flow", "extra", "leg_b", "leg_c", "surface", "_runner",
})

#: Branches that exist in `build_cell` and hand the family an input it cannot read. Declared,
#: because a wrong shape is not visible in the branch's text; each is proved by a test.
SEALED_INPUT_DEFECTS: dict[str, str] = {}


@lru_cache(maxsize=1)
def _family_table() -> dict[str, Any]:
    """name -> constructor, by the gauntlet's own two lookups (families first, then orthogonal)."""
    from mt5desk import families
    from mt5desk import families_orthogonal as fo
    out: dict[str, Any] = {}
    for name in dir(families):
        if name.startswith("family_") and callable(getattr(families, name)):
            out[name[len("family_"):]] = getattr(families, name)
    for name, fn in fo.ORTHOGONAL_FAMILIES.items():
        out.setdefault(str(name), fn)
    return out


def family_names() -> list[str]:
    try:
        return sorted(_family_table())
    except Exception:
        return []


@lru_cache(maxsize=4)
def _supplied_at(path: str, mtime_ns: int) -> frozenset[str]:
    try:
        src = Path(path).read_text("utf-8")
    except OSError:
        return frozenset()
    start = src.find("\ndef build_cell(")
    if start < 0:
        return frozenset()
    nxt = src.find("\ndef ", start + 1)
    body = src[start:nxt if nxt > 0 else len(src)]
    names: set[str] = set(re.findall(r'family\s*==\s*"([A-Za-z0-9_]+)"', body))
    for group in re.findall(r"family\s+in\s*[{(\[]([^})\]]*)[})\]]", body):
        names |= set(re.findall(r'"([A-Za-z0-9_]+)"', group))
    return frozenset(names)


def supplied_families(path: Path | None = None) -> frozenset[str]:
    """Families whose data inputs `build_cell` loads, read from its own source text."""
    p = path or SEALED_GAUNTLET
    try:
        mtime = p.stat().st_mtime_ns
    except OSError:
        return frozenset()
    return _supplied_at(str(p), mtime)


def _signature_needs(fn: Any) -> tuple[list[str], list[str]]:
    """(data inputs the family reads, parameters it REQUIRES a cell to carry)."""
    try:
        params = list(inspect.signature(fn).parameters.values())[1:]
    except (TypeError, ValueError):
        return [], []
    data: list[str] = []
    required: list[str] = []
    for p in params:
        if p.kind not in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY) or p.name == "side":
            continue
        if p.name in DATA_INPUT_ARGS:
            data.append(p.name)
        elif p.default is inspect.Parameter.empty:
            required.append(p.name)
    return data, required


@lru_cache(maxsize=256)
def family_verdict(family: str) -> tuple[str, str]:
    """`(verdict, why)` for a family, independent of any one cell's parameters."""
    fam = str(family or "").strip()
    if not fam:
        return NO_IMPLEMENTATION, "no family named"
    try:
        from research.family_policy import ban_reason, family_banned
        if family_banned(fam):
            return BANNED, ban_reason(fam)
    except Exception:
        pass
    try:
        table = _family_table()
    except Exception as exc:
        return UNMEASURED, f"families unimportable ({type(exc).__name__}: {exc})"
    fn = table.get(fam)
    if fn is None:
        return NO_IMPLEMENTATION, (f"no `family_{fam}` in families and no {fam!r} in "
                                   "ORTHOGONAL_FAMILIES -- the gauntlet's two lookups fail")
    if fam in SEALED_INPUT_DEFECTS:
        return SEALED_INPUT_DEFECT, SEALED_INPUT_DEFECTS[fam]
    data, _required = _signature_needs(fn)
    if data:
        supplied = supplied_families()
        if not supplied:
            return UNMEASURED, "the sealed gauntlet's build_cell source is unreadable here"
        if fam not in supplied:
            return INPUT_NOT_SUPPLIED, (
                f"{fam} reads data input(s) {data} and external_gauntlet.build_cell has no "
                f"branch that loads them, so the family is called with None and every cell "
                f"builds with ZERO signals. Remedy (principal-gated, the gauntlet is sealed): "
                f"a build_cell branch for {fam}.")
    return BUILDABLE, "the gauntlet resolves the family and supplies every data input it reads"


def symbol_required(family: str) -> bool:
    """True when the family builds NOTHING unless the cell itself carries `symbol`.

    MEASURED 2026-09-30: `family_cross_sectional_class_momentum` on EURUSD returns 0 signals at
    its default `symbol=""` and 729 with `symbol="EURUSD"`. The sealed `build_cell` supplies
    `symbol` to exactly one family (`carry`), so for the class books -- which load their own peer
    panel keyed by nothing but that parameter -- a cell that does not carry it is judged on an
    empty signal list: the fallback, not the mechanism. `breadth_sweep` minted such cells at the
    families' defaults on every lane symbol. The set is `universe_policy.CROSS_SECTIONAL_FAMILIES`
    (the families that read their class from `symbol`), pinned by a test that builds each."""
    try:
        from research.universe_policy import CROSS_SECTIONAL_FAMILIES
    except Exception:
        return False
    return str(family) in CROSS_SECTIONAL_FAMILIES


@lru_cache(maxsize=256)
def _required(family: str) -> tuple[str, ...]:
    try:
        return tuple(_signature_needs(_family_table()[family])[1])
    except Exception:
        return ()


def cell_verdict(family: str, params: dict[str, Any] | None = None,
                 timeframe: str | None = None) -> tuple[str, str]:
    """`(verdict, why)` for one cell: the family's verdict, then its chart, then its params."""
    verdict, why = family_verdict(family)
    if verdict != BUILDABLE:
        return verdict, why
    p = dict(params or {})
    tf = str(timeframe or p.get("timeframe") or "H1").upper()
    try:
        from mt5desk.families_orthogonal import timeframe_refusal
        refused = timeframe_refusal(str(family), tf)
    except Exception:
        refused = None
    if refused:
        return TIMEFRAME_REFUSED, refused
    missing = [r for r in _required(str(family)) if r not in p]
    if symbol_required(str(family)) and not p.get("symbol"):
        missing.append("symbol")
    if missing:
        return MISSING_PARAMS, f"{family} requires {missing} and the cell does not carry them"
    if family == "clock_transition":
        from mt5desk.family_clock_transition import CATALOGUE, MODES
        label, hour = p.get("label"), p.get("stamp_hour")
        if label not in CATALOGUE:
            return MISSING_PARAMS, "clock_transition requires a named catalogue label"
        if isinstance(hour, bool) or not isinstance(hour, int) or not 0 <= hour <= 23:
            return MISSING_PARAMS, "clock_transition requires an explicit broker stamp_hour 0..23"
        if p.get("mode", "out_of") not in MODES:
            return MISSING_PARAMS, "clock_transition mode is not in its registered modes"
    return BUILDABLE, why


def census() -> dict[str, dict[str, str]]:
    """Every family the gauntlet can resolve, with its verdict -- the table producers read."""
    out: dict[str, dict[str, str]] = {}
    for fam in family_names():
        v, why = family_verdict(fam)
        out[fam] = {"verdict": v, "why": why}
    return out
