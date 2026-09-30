"""THE KOREA MINER REGISTRY -- the twelve agents, the lattice, the interaction miner and credit.

FIFTEEN MINERS, FOUR MODULES, ONE TABLE. `MINERS` maps a miner name to `callable(ctx) -> dict`,
which is the contract `region_department.load_region` and `country_lab.run_lab` both read. The
twelve agents come from `agents.py`, the lattice expansion from `lattice.py`, and the interaction
miner and delayed source credit from `moat.py`.

WHY `MISSING` EXISTS ALONGSIDE `MINERS`. A department that silently drops a miner does not look
broken -- it looks like a department with fewer miners, and its coverage report stays internally
consistent while a whole lane is dead for a month. So `MINERS` and `MISSING` PARTITION `NAMES`
(`set(MINERS) | set(MISSING) == set(NAMES)` is a property the tests assert), and `run_miner` on a
name that did not resolve returns a RESULT whose `why` is the ImportError -- never a KeyError a
caller might catch and ignore.

THE FOUR OUTCOMES ARE ALL RESULTS. It ran; it is MISSING; it raised; it overran. None of them is
an exception out of `run_miner`, because a pass that reports on fifteen miners even when one is
broken is the only kind that can report on the other fourteen -- and a miner that takes the pass
down is a miner that hides them.

    python desks/mt5/research/countries/kr/miners.py --list
    python desks/mt5/research/countries/kr/miners.py --run macro_brain --budget-s 60 --dry-run
    python desks/mt5/research/countries/kr/miners.py --run-all --dry-run
"""
from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import sys
import time
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve()
DESK = _HERE.parents[3]
REPO = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REGION = "kr"
TAG = "kr:"
UNMEASURED = "UNMEASURED"
BUDGET_S = 240.0

#: The package roots a sibling of this module may live under. The department is imported as
#: `desks.mt5.research.countries.kr.*` by the framework, as `research.countries.kr.*` by the
#: desk's own path, and by FILE PATH with a synthetic module name by `region_department` -- which
#: is why a relative import would be the one thing that cannot work here.
PACKAGE_ROOTS: tuple[str, ...] = ("desks.mt5.research.countries.kr", "research.countries.kr",
                                  "countries.kr", "kr", "")


def _import(module: str) -> Any:
    last: Exception | None = None
    for root in PACKAGE_ROOTS:
        try:
            return importlib.import_module(f"{root}.{module}" if root else module)
        except Exception as exc:
            last = exc
    raise ImportError(f"{module}: {last}")


#: THE FIFTEEN, as (miner name, module, attribute). The twelve agents are named by their agent
#: name so `generator = "kr:<name>"` and the miner name are THE SAME STRING -- a department whose
#: budget table and whose yield table key on different names cannot pay its own miners.
SPECS: tuple[tuple[str, str, str], ...] = (
    ("macro_brain", "agents", "agent_macro_brain"),
    ("derivatives_brain", "agents", "agent_derivatives_brain"),
    ("trade_nowcaster", "agents", "agent_trade_nowcaster"),
    ("corporate_event_brain", "agents", "agent_corporate_event_brain"),
    ("retail_ecology_brain", "agents", "agent_retail_ecology_brain"),
    ("quant_code_hunter", "agents", "agent_quant_code_hunter"),
    ("academic_hunter", "agents", "agent_academic_hunter"),
    ("broker_research_hunter", "agents", "agent_broker_research_hunter"),
    ("failure_miner", "agents", "agent_failure_miner"),
    ("translation_concept", "agents", "agent_translation_concept"),
    ("source_scout", "agents", "agent_source_scout"),
    ("converter", "agents", "agent_converter"),
    ("lattice", "lattice", "expand_all"),
    ("interaction", "moat", "interaction_miner"),
    ("credit", "moat", "credit_survivors"),
    # THE FIVE MOAT STORES THEMSELVES (Tier-1 K2). `interaction_miner` and `credit_survivors`
    # are two lanes OF the moat; `moat.build` is what writes the store the department's artifact
    # names (`data/countries/kr/moat.json`). It ran nowhere, so the five stores existed as code
    # and as no file -- the classic dark organ. It is a miner like the others, and its output is
    # counted like the others.
    ("moat_stores", "moat", "build"),
)
NAMES: tuple[str, ...] = tuple(name for name, _m, _a in SPECS)

#: Which loop step each miner runs under, in `region_department.MINER_STEP`'s vocabulary. A miner
#: that belongs to no step is a miner the loop never schedules, which is the quiet way a lane
#: dies; this table is what a test can assert is total.
MINER_KIND: dict[str, str] = {
    "macro_brain": "mechanism", "derivatives_brain": "mechanism",
    "trade_nowcaster": "data", "corporate_event_brain": "mechanism",
    "retail_ecology_brain": "mechanism", "quant_code_hunter": "scout",
    "academic_hunter": "scout", "broker_research_hunter": "scout",
    "failure_miner": "failure", "translation_concept": "mechanism",
    "source_scout": "scout", "converter": "mechanism",
    "lattice": "mechanism", "interaction": "transfer", "credit": "residual",
    "moat_stores": "residual",
}

MINERS: dict[str, Callable[[Any], dict[str, Any]]] = {}
MISSING: dict[str, str] = {}


def _wrap_lattice(fn: Callable[..., dict[str, Any]]) -> Callable[[Any], dict[str, Any]]:
    """`lattice.expand_all(ctx)` in miner shape: discoveries listed, counts reported."""

    def mine_lattice(ctx: Any) -> dict[str, Any]:
        report = fn(ctx, record=not bool(getattr(ctx, "dry_run", False)))
        children = [c for row in report.get("mechanisms", []) for c in (row.get("children") or [])]
        unmeasured = [u for row in report.get("mechanisms", [])
                      for u in (row.get("unmeasured") or [])]
        totals = report.get("totals") or {}
        return {"agent": "lattice", "region": REGION,
                "discoveries": [str(c.get("discovery_id") or "") for c in children
                                if c.get("discovery_id")],
                "n_discoveries": sum(1 for c in children if c.get("discovery_id")),
                "unmeasured": unmeasured,
                "why": (f"{totals.get('chosen', 0)} child(ren) chosen from "
                        f"{totals.get('considered', 0)} lattice member(s) by prior x EVIG; "
                        f"{totals.get('refused_by_prior', 0)} refused by prior, "
                        f"{totals.get('deferred', 0)} deferred and owed"),
                "totals": totals, "selectivity": report.get("selectivity"),
                "info_gain_source": report.get("info_gain_source"),
                "mechanisms": [{k: v for k, v in row.items() if k != "children"}
                               for row in report.get("mechanisms", [])]}

    return mine_lattice


def _wrap_interaction(fn: Callable[..., dict[str, Any]]) -> Callable[[Any], dict[str, Any]]:
    def mine_interaction(ctx: Any) -> dict[str, Any]:
        report = fn(ctx, record=not bool(getattr(ctx, "dry_run", False)))
        return {"agent": "interaction", "region": REGION,
                "discoveries": list(report.get("discoveries") or []),
                "n_discoveries": int(report.get("n_discoveries") or 0),
                "unmeasured": list(report.get("unmeasured") or []),
                "why": (f"{report.get('n_triples', 0)} KR x JP x CN triple(s); "
                        f"{report.get('screens_measured', 0)} screened with a permutation null, "
                        "the rest UNMEASURED by the leg that is absent"),
                "triples": report.get("triples", [])}

    return mine_interaction


def _wrap_credit(fn: Callable[..., dict[str, Any]]) -> Callable[[Any], dict[str, Any]]:
    def mine_credit(ctx: Any) -> dict[str, Any]:
        if bool(getattr(ctx, "dry_run", False)):
            return {"agent": "credit", "region": REGION, "discoveries": [], "n_discoveries": 0,
                    "unmeasured": [{"what": "credit", "verdict": UNMEASURED,
                                    "why": "dry run: the feedback arrow writes counters, so it "
                                           "does nothing rather than pretending to"}],
                    "why": "dry run"}
        report = fn(getattr(ctx, "conn", None))
        return {"agent": "credit", "region": REGION, "discoveries": [], "n_discoveries": 0,
                "unmeasured": ([] if report.get("status") == "MEASURED"
                               else [{"what": "credit", "verdict": UNMEASURED,
                                      "why": str(report.get("why") or "")}]),
                "why": str(report.get("why") or ""), "credit": report}

    return mine_credit


def _wrap_moat(fn: Callable[..., dict[str, Any]]) -> Callable[[Any], dict[str, Any]]:
    """`moat.build(ctx)` in miner shape. A dry run BUILDS and does not WRITE, so the stores can
    be measured without touching the file the department publishes."""

    def mine_moat_stores(ctx: Any) -> dict[str, Any]:
        dry = bool(getattr(ctx, "dry_run", False))
        report = fn(ctx, getattr(ctx, "conn", None), write=not dry)
        stores = report.get("stores") if isinstance(report.get("stores"), dict) else {}
        return {"agent": "moat_stores", "region": REGION, "discoveries": [], "n_discoveries": 0,
                "unmeasured": list(report.get("unmeasured") or []),
                "why": (f"{len(stores)} moat store(s) built"
                        + (" (dry run: nothing written)" if dry else
                           f" -> {report.get('written')}")),
                "stores": {k: (v.get("n") if isinstance(v, dict) else None)
                           for k, v in stores.items()},
                "written": report.get("written")}

    return mine_moat_stores


_WRAPPERS: dict[str, Callable[[Callable[..., dict[str, Any]]], Callable[[Any], dict[str, Any]]]]
_WRAPPERS = {"lattice": _wrap_lattice, "interaction": _wrap_interaction, "credit": _wrap_credit,
             "moat_stores": _wrap_moat}


def _context(ctx: Any) -> tuple[Any, str]:
    """This department's own context, from whatever the caller handed over.

    `region_department` hands its `Ctx` and `country_lab` hands a `LabCtx`, and neither is this
    package's. The parts that MAP are the registry connection, the time box and the dry-run flag;
    the parts that do not are the readers (`ctx.claims`, `ctx.keys`, `ctx.universe`, the KR series
    ids). So a foreign context is ADAPTED -- a fresh KR context seeded from what does map -- and
    the adaptation is NAMED in the result rather than performed silently, because an agent
    running against half a context and reporting a clean pass is worse than one that did not run.
    """
    if hasattr(ctx, "record_discovery") and hasattr(ctx, "claims") and hasattr(ctx, "keys"):
        return ctx, ""
    adapted = make_ctx(getattr(ctx, "conn", None),
                       float(getattr(ctx, "budget_s", BUDGET_S) or BUDGET_S),
                       dry_run=bool(getattr(ctx, "dry_run", False)))
    return adapted, (f"the caller handed a {type(ctx).__name__}, which is not this department's "
                     "context: a fresh KR context was built from its conn, budget and dry-run "
                     "flag, and its own readers were NOT used")


def _as_miner(name: str, fn: Callable[[Any], dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    """One miner under BOTH calling conventions on this tree.

    `region_department` calls `MINERS[name](ctx)`; `country_lab.load_custom_miners` resolves a
    `module:function` entry and calls `fn(pack, ctx)`. The context is the LAST positional
    argument in both, which is the whole trick -- and it is worth the trick, because the
    alternative is a department that is wired into one scheduler and inert under the other.
    """

    def mine(*args: Any, **kwargs: Any) -> dict[str, Any]:
        handed = kwargs.get("ctx") if "ctx" in kwargs else (args[-1] if args else None)
        if handed is None:
            raise TypeError(f"mine_{name}() needs a context: called with no positional argument "
                            "and no ctx= keyword")
        ctx, adapted = _context(handed)
        if hasattr(ctx, "agent"):
            ctx.agent = name
        out = dict(fn(ctx))
        if adapted:
            out.setdefault("unmeasured", [])
            out["unmeasured"] = [*out["unmeasured"],
                                 {"what": f"miner:{name}:context", "verdict": UNMEASURED,
                                  "why": adapted}]
        return out

    mine.__name__ = f"mine_{name}"
    mine.__qualname__ = f"mine_{name}"
    mine.__doc__ = (f"The KR `{name}` miner. Accepts `(ctx)` (region_department) or "
                    f"`(pack, ctx)` (country_lab); a foreign context is adapted and the "
                    "adaptation is reported as UNMEASURED rather than hidden.")
    return mine


def refresh() -> tuple[dict[str, Callable[[Any], dict[str, Any]]], dict[str, str]]:
    """Resolve every declared miner, NAME what could not be resolved, and publish `mine_<name>`.

    Re-runnable on purpose: the four modules of this package are written by four builders, so a
    tree where `moat.py` lands an hour after this file must pick the interaction miner up without
    a restart. The partition `MINERS | MISSING == NAMES` holds after every call, and every
    resolved miner is ALSO a module-level `mine_<name>` so a `country_lab` pack can name it as
    `desks.mt5.research.countries.kr.miners:mine_<name>`.
    """
    MINERS.clear()
    MISSING.clear()
    for name, module, attribute in SPECS:
        globals().pop(f"mine_{name}", None)
        try:
            mod = _import(module)
        except ImportError as exc:
            MISSING[name] = (f"module {module!r} is not importable under any of "
                             f"{PACKAGE_ROOTS}: {exc}. The miner is DECLARED and ABSENT, which "
                             "is a defect to fix, not a department with fewer miners")
            continue
        fn = getattr(mod, attribute, None)
        if not callable(fn):
            MISSING[name] = (f"{module}:{attribute} is not callable: the module landed without "
                             "this miner, so the declaration has no implementation")
            continue
        wrapper = _WRAPPERS.get(name)
        resolved = wrapper(fn) if wrapper is not None else fn
        entry = _as_miner(name, resolved)
        MINERS[name] = entry
        globals()[f"mine_{name}"] = entry
    return MINERS, MISSING


#: The `module:function` entries a `country_lab` pack declares to reach this department.
CUSTOM_MINER_ENTRIES: tuple[str, ...] = tuple(
    f"desks.mt5.research.countries.kr.miners:mine_{name}" for name in NAMES)

refresh()


def make_ctx(conn: Any = None, budget_s: float = BUDGET_S, **kwargs: Any) -> Any:
    """THE ONE CONTEXT PER PASS, built by `agents.make_ctx`.

    Re-exported here because the region framework reaches for `miners.make_ctx` and the agents
    own the context's shape; two `make_ctx` implementations would be two departments.
    """
    agents = _import("agents")
    return agents.make_ctx(conn, budget_s, **kwargs)


def run_miner(name: str, ctx: Any) -> dict[str, Any]:
    """One miner inside its time box, with a uniform result whatever happened."""
    started = time.monotonic()
    if name not in MINERS:
        refresh()
    fn = MINERS.get(name)
    if fn is None:
        why = MISSING.get(name) or (f"{name!r} is not a KR miner name; the fifteen are "
                                    f"{', '.join(NAMES)}")
        return {"miner": name, "region": REGION, "seconds": 0.0, "discoveries": [],
                "unmeasured": [{"what": f"miner:{name}", "verdict": UNMEASURED, "why": why}],
                "why": why, "status": "MISSING"}
    budget = float(getattr(ctx, "budget_s", BUDGET_S) or BUDGET_S)
    if hasattr(ctx, "agent"):
        ctx.agent = name
    if hasattr(ctx, "started_at_monotonic"):
        ctx.started_at_monotonic = started
    try:
        payload = fn(ctx)
    except Exception as exc:  # a miner that raises is COUNTED, never swallowed and never fatal
        return {"miner": name, "region": REGION,
                "seconds": round(time.monotonic() - started, 3), "discoveries": [],
                "unmeasured": [{"what": f"miner:{name}", "verdict": UNMEASURED,
                                "why": f"raised {type(exc).__name__}: {exc}"}],
                "why": f"{name} raised {type(exc).__name__}: {exc}", "status": "RAISED"}
    seconds = round(time.monotonic() - started, 3)
    payload = payload if isinstance(payload, Mapping) else {}
    result: dict[str, Any] = {
        "miner": name, "region": REGION, "kind": MINER_KIND.get(name, "mechanism"),
        "seconds": seconds, "discoveries": list(payload.get("discoveries") or []),
        "unmeasured": list(payload.get("unmeasured") or []),
        "why": str(payload.get("why") or ""),
        "status": "OVERRAN" if seconds > budget else "RAN"}
    for key in ("totals", "selectivity", "triples", "credit", "steer", "registered",
                "unavailable", "concept_counts", "by_class", "memories", "converted", "blocked",
                "n_discoveries", "owed", "signal_classes", "failure_classes", "duplicate_groups"):
        if key in payload:
            result[key] = payload[key]
    if result["status"] == "OVERRAN":
        result["unmeasured"].append({
            "what": f"miner:{name}:budget", "verdict": UNMEASURED,
            "why": f"took {seconds}s against a {budget}s box: what it did not reach is OWED, "
                   "not refused"})
    return result


def run_all(ctx: Any, only: Iterable[str] | None = None) -> dict[str, Any]:
    """Every declared miner, independently. One raising costs the other fourteen nothing."""
    wanted = [n for n in NAMES if only is None or n in set(only)]
    started = time.monotonic()
    results = [run_miner(name, ctx) for name in wanted]
    return {"region": REGION, "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "seconds": round(time.monotonic() - started, 3), "n_miners": len(results),
            "resolved": sorted(MINERS), "missing": dict(MISSING),
            "by_status": {s: sum(1 for r in results if r["status"] == s)
                          for s in ("RAN", "OVERRAN", "RAISED", "MISSING")},
            "n_discoveries": sum(len(r["discoveries"]) for r in results),
            "n_unmeasured": sum(len(r["unmeasured"]) for r in results),
            "results": results,
            "rule": "a region department has ZERO capital authority: its output terminates at a "
                    "gauntlet-ready candidate, and it is never finished"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the Korea department's fifteen miners")
    ap.add_argument("--list", action="store_true", help="print the resolution table and exit")
    ap.add_argument("--run", default="", help="one miner by name")
    ap.add_argument("--run-all", action="store_true")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--dry-run", action="store_true", help="record nothing")
    a = ap.parse_args(argv)
    refresh()
    if a.list or not (a.run or a.run_all):
        print(json.dumps({"names": list(NAMES), "resolved": sorted(MINERS),
                          "missing": MISSING, "kinds": MINER_KIND}, indent=1))
        return 0
    conn = None
    if not a.dry_run:
        with contextlib.suppress(Exception):
            from libs.moat import registry as R

            conn = R.connect()
    ctx = make_ctx(conn, a.budget_s, dry_run=a.dry_run)
    out = run_all(ctx) if a.run_all else run_miner(a.run, ctx)
    print(json.dumps(out, indent=1, default=str, ensure_ascii=False)[:20000])
    return 0


__all__ = ["CUSTOM_MINER_ENTRIES", "MINERS", "MINER_KIND", "MISSING", "NAMES", "SPECS", "main",
           "make_ctx", "refresh", "run_all", "run_miner"]


if __name__ == "__main__":
    raise SystemExit(main())
