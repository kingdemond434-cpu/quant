"""THE JUDGE'S OWN CALL, CHECKED BEFORE THE ROW ENTERS THE DOCKET: missing required parameters.

WHY THIS EXISTS (Judge thread, 2026-11-24, fix G of JUDGE_100K_ROOT_CAUSE). Every sweep's
pre-warm fails the same cells the same way, measured in the box's MT5-Gauntlet.log:

    seasonal_window   TypeError "family_seasonal_window() missing 3 required keyword-only
                      arguments: 'start_md', 'end_md' and 'side_bias'"          (227 per sweep)
    mass_screen_cond  "family_mass_screen_rule() missing 6 required keyword-only arguments:
                      'feat', 'op', 'thr', 'direction', 'hold' ..."

A failed build is never stamped seen, so these cells stay at the head of the never-judged
backlog and are re-attempted FIRST on every sweep, each one loading bars and holding a pre-warm
worker before it fails. The producers that minted them were fixed on 2026-11-14
(`local_converter._required_evidence`, `independence_intake.carries_its_rule`), but the docket
re-admits its own bank on every merge (`merge_hypotheses`: "the docket now UNIONS this run's
fresh rows with everything already banked"), so the rows minted before that fix live forever.

THE CHECK IS THE JUDGE'S, NOT A NEW ONE. `scripts/external_gauntlet.build_cell` (SEALED, never
edited here) does, in this order, for a family it resolves:

    fn = getattr(families, f"family_{family}") or families_orthogonal.ORTHOGONAL_FAMILIES[family]
    call_params = dict(params)                    # + runtime inputs for the families it branches on
    call_params.pop("timeframe"); call_params.pop("session")
    call_params, mods = cell_modifiers.split(fn, call_params)
    fn(h1, side=1, **call_params)  -> on TypeError ->  fn(h1, **call_params)

Python binds the arguments before the family's body runs, so a required parameter (no default)
that `call_params` does not supply fails BOTH calls with TypeError "missing ... required ...
argument", deterministically, whatever the bars. `side` is supplied by the first call, `h1` fills
the first positional parameter. That and nothing else is what `missing_required` computes.

NEVER STRICTER THAN THE JUDGE. Two kinds of family are NEVER set aside here, because their call
carries keys this module cannot see from the row:
  * every family `build_cell` branches on to load runtime inputs (peer bars, factor panels,
    the event calendar, `symbol` for carry ...). The set is read from the sealed file's own
    source (`gauntlet_buildability.supplied_families`) plus `RAW_COT_FAMILIES`, so a re-signed
    judge that adds a branch widens the exemption with no edit here;
  * a family whose signature cannot be read, or that the judge's two lookups do not resolve
    (the judge refuses those by its own name, "no implementation of family").
Anything this module cannot evaluate keeps its row in the docket: an error here is never a
reason to remove a cell.

NEVER SILENTLY DROPPED. A row that fails goes to `unbuildable_set_aside.json` beside the docket,
stamped `judging_status = NOT_BUILDABLE_MISSING_PARAMS` with the exact names it lacks. The merge
re-reads that file on every run and re-offers its rows, so a row whose family later gains a
default (or whose producer re-donates it whole) returns to the docket on the next merge.

Revert: `data/JUDGE_BUILD_PREFLIGHT.json` = `{"enabled": false}` turns the filter off on the next
merge, and the set-aside rows flow back into the docket through the same re-offer.
"""
from __future__ import annotations

import contextlib
import inspect
import json
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
for _p in (str(BASE), str(BASE.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: The verdict stamped on a set-aside row.
STATUS = "NOT_BUILDABLE_MISSING_PARAMS"
#: The set-aside file's name; it lives beside the docket (`merge_hypotheses.HYP`).
SET_ASIDE_NAME = "unbuildable_set_aside.json"
#: The revert switch. Absent or unreadable = enabled (the filter is exactly the judge's check).
SWITCH = BASE / "data" / "JUDGE_BUILD_PREFLIGHT.json"
#: Keys this module stamps on a set-aside row, removed again when the row is re-offered.
STAMP_KEYS = ("judging_status", "judging_reason", "missing_params", "set_aside_at")
#: Keys `build_cell` pops from the call before it is made: they name the chart and the session,
#: never a family argument.
POPPED_BY_JUDGE = ("timeframe", "session")
#: The keyword argument `build_cell`'s first call supplies.
SIDE = "side"


def enabled(path: Path | None = None) -> bool:
    """False only when the switch file says `"enabled": false`."""
    try:
        doc = json.loads((path or SWITCH).read_text("utf-8"))
    except (OSError, ValueError):
        return True
    return not (isinstance(doc, dict) and doc.get("enabled") is False)


def resolve(family: str) -> Callable[..., Any] | None:
    """The constructor by the judge's own two lookups, in its order; None when neither answers."""
    try:
        from mt5desk import families
        fn = getattr(families, f"family_{family}", None)
    except Exception:
        fn = None
    if fn is None:
        try:
            from mt5desk import families_orthogonal as fo
            fn = fo.ORTHOGONAL_FAMILIES.get(family)
        except Exception:
            fn = None
    return fn


def exempt_families() -> frozenset[str] | None:
    """Families whose judge call carries runtime inputs the row does not show; None = unknown.

    Read from the sealed `build_cell` source, so the set can only follow the judge. When it
    cannot be read the answer is None and NOTHING is set aside."""
    try:
        from mt5desk.legacy_family_inputs import RAW_COT_FAMILIES

        from research.gauntlet_buildability import supplied_families
        supplied = supplied_families()
    except Exception:
        return None
    if not supplied:
        return None
    return frozenset(supplied) | frozenset(RAW_COT_FAMILIES)


def _required_after_h1(fn: Callable[..., Any]) -> list[str] | None:
    """The names Python will demand once h1 is bound positionally and `side`=1 is passed; None
    when the signature cannot be read."""
    try:
        params = list(inspect.signature(fn).parameters.values())
    except (TypeError, ValueError):
        return None
    need: list[str] = []
    h1_bound = False
    for p in params:
        if not h1_bound and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD):
            h1_bound = True          # `fn(h1, ...)`: the first positional slot is the bars
            continue
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD) or p.default is not p.empty:
            continue
        if p.name == SIDE and p.kind is not p.POSITIONAL_ONLY:
            continue                 # the first call passes side=1
        need.append(p.name)
    return need


def judge_call_params(fn: Callable[..., Any], params: dict[str, Any]) -> dict[str, Any]:
    """The keyword arguments `build_cell` hands `fn` for a family it loads no inputs for."""
    from mt5desk import cell_modifiers

    call = dict(params)
    for key in POPPED_BY_JUDGE:
        call.pop(key, None)
    call, _mods = cell_modifiers.split(fn, call)
    return call


def missing_required(family: str, params: Any,
                     exempt: frozenset[str] | None = None) -> tuple[str, ...]:
    """The required arguments the judge's call to `family` will lack; () when it binds, or when
    this module cannot tell (exempt or unresolvable family, unreadable signature, odd params)."""
    fam = str(family or "")
    ex = exempt_families() if exempt is None else exempt
    if not fam or ex is None or fam in ex:
        return ()
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return ()                    # the judge refuses this by its own name; not ours to judge
    fn = resolve(fam)
    if fn is None:
        return ()
    need = _required_after_h1(fn)
    if need is None:
        return ()
    try:
        call = judge_call_params(fn, params)
    except Exception:
        return ()
    return tuple(n for n in need if n not in call)


def reason(family: str, missing: Iterable[str]) -> str:
    names = ", ".join(repr(m) for m in missing)
    return (f"{family}: the sealed judge's build_cell calls the family without required "
            f"argument(s) {names} and fails with TypeError before any gate (NOT_RUN_BUILD_FAILED "
            f"every sweep, never stamped seen, so re-fronted every sweep). Set aside by the same "
            f"binding check; re-offered on every merge, judged once the row carries them")


def split_unbuildable(rows: list[dict[str, Any]], stamp: str
                      ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """`(keep, set_aside, report)`. Order of `keep` is the order of `rows`; nothing is dropped.

    Fails open: if the exempt set cannot be read, every row is kept and the report says so."""
    exempt = exempt_families()
    report: dict[str, Any] = {"status": "APPLIED", "checked": len(rows), "set_aside": 0,
                              "by_family": {}, "rule": STATUS}
    if exempt is None:
        report["status"] = ("UNMEASURED: the sealed build_cell source is unreadable; "
                            "nothing set aside")
        return list(rows), [], report
    keep: list[dict[str, Any]] = []
    aside: list[dict[str, Any]] = []
    memo: dict[tuple[str, tuple[str, ...]], tuple[str, ...]] = {}
    for row in rows:
        fam = str(row.get("family") or "")
        params = row.get("params")
        if params is None or isinstance(params, dict):
            key = (fam, tuple(sorted(str(k) for k in (params or {}))))
            if key not in memo:
                memo[key] = missing_required(fam, params or {}, exempt)
            miss = memo[key]
        else:
            miss = ()
        if not miss:
            keep.append(row)
            continue
        row["judging_status"] = STATUS
        row["missing_params"] = list(miss)
        row["judging_reason"] = reason(fam, miss)
        row["set_aside_at"] = stamp
        aside.append(row)
        fam_rep = report["by_family"].setdefault(fam, {"rows": 0, "missing": {}})
        fam_rep["rows"] += 1
        for m in miss:
            fam_rep["missing"][m] = fam_rep["missing"].get(m, 0) + 1
    report["set_aside"] = len(aside)
    return keep, aside, report


def read_set_aside(path: Path) -> list[dict[str, Any]]:
    """The banked set-aside rows with this module's stamps removed, ready to be re-offered.

    An unreadable file is moved aside (never overwritten) so its rows are not lost."""
    if not path.exists():
        return []
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        with contextlib.suppress(OSError):
            path.replace(path.with_name(path.name + ".unreadable"))
        return []
    if not isinstance(doc, list):
        return []
    out = []
    for row in doc:
        if isinstance(row, dict):
            out.append({k: v for k, v in row.items() if k not in STAMP_KEYS})
    return out


def write_set_aside(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(rows, indent=1, default=str), "utf-8")
    tmp.replace(path)
