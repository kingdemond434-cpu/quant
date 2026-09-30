#!/usr/bin/env python3
"""NO RESEARCH LEG RUNS WITHOUT AN EXPERIMENT CONTRACT (hypothesis, metric, falsifier, budget,
owner) -- the fence, and the hourly reading of every contract against its leg's own report.

    python scripts/check_experiment_contracts.py            the fence (law gate)
    python scripts/check_experiment_contracts.py --report   the hourly leg: evaluate and publish
    python scripts/check_experiment_contracts.py --update   rewrite the grandfather list after
                                                            legs gained their contracts

THE FENCE fails when
  * a registered hourly leg (every `_costed("<leg>", ...)` in hourly_cycle.py) is NOT in the
    grandfather list and carries no valid contract -- a NEW leg must be born contracted;
  * a declared contract does not validate (`libs.tiers.experiment_contract.problems`);
  * the grandfather list names a leg that is no longer registered, or GREW -- it may only shrink,
    so the uncontracted backlog is a number that can only be driven down.

PRE-EXISTING DEBT IS THE FLOOR, NOT A FAILURE (L1.43): the legs that existed uncontracted on the
day this fence was built are listed by NAME in `docs/research/experiment_contracts.json`
(`grandfathered`), and a leg drops out of that list the moment it gains a contract (`--update`).

THE REPORT (`--report`, hourly leg `experiment_contracts`) reads each contracted leg's own report,
records the metric into `desks/mt5/data/experiment_contract_history.jsonl`, evaluates it with the
admission rule's own `contracts.evaluate` (ADMITTED / REJECTED / UNMEASURED against its history)
and judges the falsifier (HOLDS / FALSIFIED / UNMEASURED). It writes
`desks/mt5/reports/EXPERIMENT_CONTRACTS.json`. Nothing here stops a leg or cuts a budget.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.tiers import contracts  # noqa: E402
from libs.tiers import experiment_contract as ec  # noqa: E402

OUT = ROOT / "desks" / "mt5" / "reports" / "EXPERIMENT_CONTRACTS.json"
HISTORY = ROOT / "desks" / "mt5" / "data" / "experiment_contract_history.jsonl"
#: Readings kept per leg for the admission verdict.
HISTORY_KEEP = 96


def registered_legs(root: Path | None = None) -> list[str]:
    from desks.mt5.ops import components
    return components.leg_names()


def cycle_tables() -> tuple[dict[str, int], dict[str, str], int]:
    """(LEG_BUDGET_SEC, LEG_DEPARTMENT, default budget) from the hourly cycle itself."""
    try:
        from desks.mt5.ops import components
        mod = components._hourly_module()
    except Exception:                                      # pragma: no cover - import guard
        return {}, {}, 720
    budget = {str(k): int(v) for k, v in (getattr(mod, "LEG_BUDGET_SEC", {}) or {}).items()}
    dept = {str(k): str(v) for k, v in (getattr(mod, "LEG_DEPARTMENT", {}) or {}).items()}
    return budget, dept, int(getattr(mod, "SEARCH_BUDGET_SEC", 720) or 720)


def contracts_for(legs: list[str], registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    budget, dept, default_budget = cycle_tables()
    ts = ec.tier_s_metrics()
    declared = registry.get("legs") or {}
    out: dict[str, dict[str, Any]] = {}
    for leg in legs:
        out[leg] = ec.resolve(leg, declared.get(leg), budget_s=budget.get(leg, default_budget),
                              department=dept.get(leg, "rest"), tier_s_metric=ts.get(leg))
    return out


def check(registry: dict[str, Any], legs: list[str],
          resolved: dict[str, dict[str, Any]]) -> tuple[list[str], dict[str, Any]]:
    problems: list[str] = []
    grand = set(registry.get("grandfathered") or [])
    declared = registry.get("legs") or {}
    valid = {leg for leg, c in resolved.items() if not ec.problems(c)}
    for leg in legs:
        if leg in valid or leg in grand:
            continue
        why = "; ".join(ec.problems(resolved[leg]))
        problems.append(f"leg {leg}: registered with no valid experiment contract ({why})")
    for leg in sorted(declared):
        if leg not in resolved:
            problems.append(f"leg {leg}: contract declared for a leg that is not registered")
            continue
        for p in ec.problems(resolved[leg]):
            problems.append(f"leg {leg}: {p}")
    for leg in sorted(grand):
        if leg not in legs:
            problems.append(f"grandfathered leg {leg} is no longer registered: remove it "
                            "(--update)")
    ceiling = registry.get("grandfathered_max")
    if isinstance(ceiling, int) and len(grand) > ceiling:
        problems.append(f"grandfather list grew to {len(grand)} above its ratchet {ceiling}: "
                        "the uncontracted backlog may only shrink")
    healed = sorted(grand & valid)
    summary = {"registered": len(legs), "contracted": len(valid & set(legs)),
               "grandfathered": len(grand), "healed_awaiting_update": healed,
               "coverage": round(len(valid & set(legs)) / len(legs), 6) if legs else None}
    return problems, summary


def _history(path: Path) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                for leg, v in (r.get("values") or {}).items():
                    if isinstance(v, (int, float)):
                        out.setdefault(leg, []).append(float(v))
    except OSError:
        return {}
    return {k: v[-HISTORY_KEEP:] for k, v in out.items()}


def report(resolved: dict[str, dict[str, Any]], summary: dict[str, Any],
           problems: list[str], history_path: Path = HISTORY) -> dict[str, Any]:
    hist = _history(history_path)
    rows: dict[str, Any] = {}
    values: dict[str, float] = {}
    for leg, c in sorted(resolved.items()):
        if ec.problems(c):
            continue
        doc, how = ec.report_for(c)
        m = c["metric"]
        val = contracts.read_metric(doc, str(m.get("metric"))) if doc else None
        if val is not None:
            values[leg] = val
        series = [*hist.get(leg, []), *([val] if val is not None else [])]
        verdict = contracts.evaluate(contracts.Contract.parse(m), series)
        rows[leg] = {"hypothesis": c.get("hypothesis"), "owner": c.get("owner"),
                     "budget": c.get("budget"), "metric": m, "latest": val,
                     "report": how, "verdict": verdict,
                     "falsifier": ec.judge_falsifier(c, doc) if doc
                     else {"verdict": ec.UNMEASURED, "why": how},
                     "derived": c.get("derived", {})}
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": now, "values": values}, sort_keys=True) + "\n")
    except OSError:
        pass
    count = lambda key, v: sum(1 for r in rows.values()  # noqa: E731
                               if (r[key] or {}).get("verdict") == v)
    return {
        "schema": "experiment-contracts/1", "at": now, **summary,
        "fence_problems": problems,
        "verdicts": {v: count("verdict", v) for v in ("ADMITTED", "REJECTED", "UNMEASURED")},
        "falsifiers": {v: count("falsifier", v) for v in (ec.HOLDS, ec.FALSIFIED,
                                                          ec.UNMEASURED)},
        "falsified": sorted(k for k, r in rows.items()
                            if (r["falsifier"] or {}).get("verdict") == ec.FALSIFIED),
        "contracts": rows,
        "rule": ("a falsified experiment is published for its owner to answer; nothing here "
                 "stops a leg, cuts a budget or removes a producer"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report", action="store_true", help="evaluate and publish (hourly leg)")
    ap.add_argument("--update", action="store_true",
                    help="drop healed legs from the grandfather list and lower its ratchet")
    ap.add_argument("--registry", type=Path, default=ec.REGISTRY)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    registry = ec.load_registry(a.registry)
    if not registry:
        print(f"experiment contracts: {a.registry} absent or unreadable")
        return 2
    legs = registered_legs()
    resolved = contracts_for(legs, registry)
    problems, summary = check(registry, legs, resolved)
    if a.update:
        grand = sorted((set(registry.get("grandfathered") or [])
                        - set(summary["healed_awaiting_update"])) & set(legs))
        registry["grandfathered"] = grand
        registry["grandfathered_max"] = len(grand)
        a.registry.write_text(json.dumps(registry, indent=1, ensure_ascii=False) + "\n", "utf-8")
        print(f"experiment contracts: grandfather list now {len(grand)}")
        problems, summary = check(registry, legs, resolved)
    print(f"experiment contracts: {summary['registered']} registered legs, "
          f"{summary['contracted']} contracted, {summary['grandfathered']} grandfathered "
          f"(coverage {summary['coverage']})")
    for p in problems:
        print(f"  BREACH: {p}")
    if a.report:
        doc = report(resolved, summary, problems)
        a.out.parent.mkdir(parents=True, exist_ok=True)
        tmp = a.out.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str), "utf-8")
        tmp.replace(a.out)
        print(f"  -> {a.out} (falsified: {len(doc['falsified'])})")
        return 0                                   # the leg publishes; the fence is the law gate
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
