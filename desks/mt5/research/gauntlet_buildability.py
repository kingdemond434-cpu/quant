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
    # HUNT16 IS A THIRD POPULATION THE JUDGE RESOLVES. `families.__getattr__` exposes each one as
    # `family_<name>`, which is exactly the judge's `getattr(families, ...)` lookup -- but `dir()`
    # never lists a module `__getattr__` name, so this table called `dav_range_filter_adx`
    # NO_IMPLEMENTATION while the judge built it (measured 2026-10-06: it raised on a string
    # `side` instead). Read the same population the judge reads.
    try:
        from mt5desk.executables import hunt16_families
        for name, fn in hunt16_families().items():
            if callable(getattr(families, f"family_{name}", None)):
                out.setdefault(str(name), fn)
    except Exception:
        pass
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
    if missing:
        return MISSING_PARAMS, f"{family} requires {missing} and the cell does not carry them"
    if _requires_side(str(family)):
        side = p.get("side")
        if isinstance(side, bool) or side not in (1, -1):
            return MISSING_PARAMS, (f"{family} takes a REQUIRED numeric side (+1/-1) and the "
                                    f"cell carries {side!r}")
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


@lru_cache(maxsize=256)
def _requires_side(family: str) -> bool:
    """`side` is skipped by `_signature_needs` (most families default it); a family that has NO
    default for it -- the hunt16 population -- must carry a numeric one."""
    try:
        fn = _family_table()[family]
        prm = inspect.signature(fn).parameters.get("side")
    except Exception:
        return False
    return prm is not None and prm.default is inspect.Parameter.empty


#: Verdicts that mean the sealed judge cannot rule this cell as written. A row holding one is
#: never dispatched; it is charged in the trial census through the screened-refused ledger.
#: UNMEASURED and BANNED are NOT here: absence never refuses (L1.28a), and banned families have
#: their own study-bank route.
REFUSED_VERDICTS: frozenset[str] = frozenset({
    NO_IMPLEMENTATION, INPUT_NOT_SUPPLIED, SEALED_INPUT_DEFECT, TIMEFRAME_REFUSED, MISSING_PARAMS})

#: A claim about commercial COT positioning reaches the judge through the one COT conditioner
#: the sealed build path supplies (`cot_positioning`, which it hands the point-in-time frame).
COT_CONDITIONER = "cot_positioning"
COT_ROUTED: frozenset[str] = frozenset({"cot_comm_follow", "cot_change_momentum"})

_SIDE_WORDS = {"LONG": 1, "BUY": 1, "BULL": 1, "SHORT": -1, "SELL": -1, "BEAR": -1}


def normalise_side(value: Any) -> Any:
    """'SHORT'/'SELL' -> -1, 'LONG'/'BUY' -> +1, numeric strings to int; anything else unchanged."""
    if isinstance(value, str):
        v = value.strip().upper()
        if v in _SIDE_WORDS:
            return _SIDE_WORDS[v]
        if v in {"1", "+1", "-1"}:
            return int(v)
    if isinstance(value, float) and value in (1.0, -1.0):
        return int(value)
    return value


def _broker_offset() -> int:
    try:
        from research.session_phase import broker_utc_offset_h
        return int(broker_utc_offset_h()[0])
    except Exception:
        return 2          # the measured winter anchor (CLAUDE.md, the seven sleeves' clocks)


def repair_cell(family: str, params: dict[str, Any] | None = None
                ) -> tuple[list[tuple[str, dict[str, Any]]], str]:
    """Re-express a minted cell so the sealed judge can build it, WITHOUT changing its claim.

    Returns `([(family, params), ...], note)`. Every returned cell is BUILDABLE by `cell_verdict`;
    an empty list means it could not be repaired and `note` says why (the caller keeps the row so
    the merge screen charges it). The repairs, each the producer-side root of a measured
    build-failure class (2026-10-06 docket probe):
      * a chart the family declares inexpressible -> one cell per chart it DOES declare;
      * `clock_transition` with no stamp hour -> one cell per broker stamp hour of its label;
      * `calendar_month` with no month/direction -> the 12 x 2 month/side grid (all charged);
      * the two COT claims -> `cot_positioning`, the COT conditioner the judge supplies;
      * a worded side ('SHORT') -> its numeric convention.
    """
    fam = str(family or "")
    p = dict(params or {})
    note: list[str] = []
    if "side" in p:
        side = normalise_side(p["side"])
        if side != p["side"]:
            note.append(f"side {p['side']!r} -> {side}")
            p["side"] = side
    if fam in COT_ROUTED:
        note.append(f"{fam} reads a COT frame the judge never loads for it; routed to "
                    f"{COT_CONDITIONER}, which it does")
        fam = COT_CONDITIONER
        p = {k: v for k, v in p.items() if k in {"timeframe", "session"}}
        p["input_source"] = "cot_point_in_time"
    variants: list[dict[str, Any]] = [p]
    if fam == "clock_transition":
        hour = p.get("stamp_hour")
        if isinstance(hour, bool) or not isinstance(hour, int) or not 0 <= hour <= 23:
            try:
                from mt5desk.family_clock_transition import stamp_hours_for
                hours = stamp_hours_for(str(p.get("label") or ""), _broker_offset())
            except Exception:
                hours = ()
            if hours:
                variants = [{**p, "stamp_hour": int(h)} for h in hours]
                note.append(f"stamp_hour from the catalogue: {list(hours)}")
    if fam == "calendar_month" and not ({"active_month", "side_bias"} <= set(p)):
        variants = [{**p, "active_month": m, "side_bias": sd}
                    for m in range(1, 13) for sd in (1, -1)
                    if p.get("active_month", m) == m and p.get("side_bias", sd) == sd]
        note.append(f"calendar_month carried no month/direction: {len(variants)} explicit "
                    "cell(s), every one charged")
    tf = str(p.get("timeframe") or "H1").upper()
    try:
        from mt5desk.families_orthogonal import timeframe_domain, timeframe_refusal
        if timeframe_refusal(fam, tf):
            domain = timeframe_domain(fam)
            variants = [{**{k: v for k, v in v0.items() if k != "timeframe"},
                         **({"timeframe": t} if t != "H1" else {})}
                        for v0 in variants for t in domain]
            note.append(f"{tf} is not a chart {fam} can express; re-homed to {list(domain)}")
    except Exception:
        pass
    out: list[tuple[str, dict[str, Any]]] = []
    why = ""
    for v in variants:
        verdict, why = cell_verdict(fam, v, v.get("timeframe"))
        if verdict == BUILDABLE:
            out.append((fam, v))
    if not out:
        return [], why or "no buildable re-expression"
    return out, "; ".join(note)


def screen_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]],
                                                     list[dict[str, Any]]]:
    """(dispatchable, refused): refused rows carry `refusal_verdict` / `refusal_reason`. A row
    whose verdict cannot be read is DISPATCHED -- absence never refuses (L1.28a)."""
    keep: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    for row in rows:
        p = row.get("params") if isinstance(row.get("params"), dict) else {}
        try:
            verdict, why = cell_verdict(str(row.get("family") or ""), p,
                                        p.get("timeframe") or row.get("timeframe"))
        except Exception:
            keep.append(row)
            continue
        if verdict in REFUSED_VERDICTS:
            refused.append({**row, "refusal_verdict": verdict, "refusal_reason": why})
        else:
            keep.append(row)
    return keep, refused


def census() -> dict[str, dict[str, str]]:
    """Every family the gauntlet can resolve, with its verdict -- the table producers read."""
    out: dict[str, dict[str, str]] = {}
    for fam in family_names():
        v, why = family_verdict(fam)
        out[fam] = {"verdict": v, "why": why}
    return out
