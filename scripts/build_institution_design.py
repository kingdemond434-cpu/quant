#!/usr/bin/env python3
"""ONE CONSOLIDATED DESIGN, DERIVED FROM THE CODE: interfaces, timing, state ownership,
uncertainty, failure handling and resource budgets, with every contradiction between them named
and the precedence rule that resolves it.

    python scripts/build_institution_design.py            # hourly leg `institution_design`
    python scripts/build_institution_design.py --render   # also rewrite the committed design

WHY (ARCH-31, principal 2026-10-07: "produce one consolidated design that specifies interfaces,
timing, state ownership, uncertainty, failure handling and resource budgets, and resolves
contradictory policies, instead of more addenda"). The desk's design lives in hundreds of
docstrings, a component registry, a capability graph, two manifests and a stack of dated
addenda. Another hand-written document would be one more addendum and would rot in a week.

So the design is DERIVED. `desks/mt5/ops/components.registry()` already declares, per component,
its inputs, outputs, consumers, owner, schedule, cadence, max silence, restart action,
criticality and resource budget. This file reads that one registry, plus the hourly cycle's leg
budgets and floors and the experiment contracts, and writes:

    desks/mt5/reports/INSTITUTION_DESIGN.json   every hour, on the box
    docs/research/INSTITUTION_DESIGN.md         on --render: the committed, readable design

CONTRADICTIONS ARE COMPUTED, NOT LISTED BY HAND, and each class carries its resolution:

    CONTESTED_STATE      two organs (different code) declare the same output path. Resolution:
                         a path has ONE owner -- the producer the capability graph names, else
                         the first registered; every other writer takes its own filename.
    STALE_BY_DESIGN      a consumer's max silence is shorter than its input producer's cadence,
                         so it is guaranteed to read a late input. Resolution: the CONSUMER's
                         tolerance governs; the producer's clock must rise to it or the consumer
                         must read the input as UNMEASURED past the producer's silence.
    BUDGET_BELOW_FLOOR   a leg's base budget sits under its declared floor. Resolution: the floor
                         wins (it is the organ's own stopping point; `_producer_impl` applies it).
    DEAD_BUDGET          a leg budget for a leg the cycle never costs. Resolution: remove it.
    METRIC_DIRECTION     two experiment contracts read the same report metric and want it to move
                         in opposite directions. Resolution: the principal's objective
                         (E[log W]) decides; until then both stand and the pair is named.
    REGISTRY_PROBLEM     the registry's own structural lies (`Registry.problems`).

UNMEASURED is written as such: a component with no declared cadence is counted, not guessed.
Report only -- nothing is retired, rescheduled or rewritten by this file.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = DESK / "reports" / "INSTITUTION_DESIGN.json"
DOC = ROOT / "docs" / "research" / "INSTITUTION_DESIGN.md"
CONTRACTS = ROOT / "docs" / "research" / "experiment_contracts.json"
HOURLY = DESK / "research" / "hourly_cycle.py"

RESOLUTION = {
    "CONTESTED_STATE": "one owner per path: the capability graph's producer, else the first "
                       "registered; every other writer takes its own filename",
    "STALE_BY_DESIGN": "the consumer's tolerance governs: raise the producer's clock or read the "
                       "input as UNMEASURED past the producer's silence",
    "BUDGET_BELOW_FLOOR": "the floor wins (the organ's own stopping point; applied by "
                          "hourly_cycle._producer_impl)",
    "DEAD_BUDGET": "remove the budget line: a leg the cycle never costs spends nothing",
    "METRIC_DIRECTION": "the objective (robust forward E[log W]) decides; both stand and the "
                        "pair is named until it does",
    "REGISTRY_PROBLEM": "fix the registry entry: a declared component must be true",
}


def _specs() -> list[Any]:
    from ops import components
    return list(components.registry().all())


def _primary_code(s: Any) -> str:
    """The organ behind a component: its last code path (a leg's producer, not hourly_cycle)."""
    paths = [p for p in s.code_paths if not p.endswith("hourly_cycle.py")]
    return (paths or list(s.code_paths) or [s.component_id])[-1]


def _graph_owner() -> dict[str, str]:
    try:
        from libs.ops.capability_graph import NODES
    except Exception:
        return {}
    out: dict[str, str] = {}
    for n in NODES:
        for w in n.writes:
            out.setdefault(w, n.module)
    return out


_GRAPH_READS: dict[str, tuple[str, ...]] | None = None


def _inputs(s: Any) -> tuple[str, ...]:
    """A component's declared inputs plus what the capability graph says its module reads (the
    registry declares inputs for few components; the graph is the second declared source)."""
    global _GRAPH_READS
    if _GRAPH_READS is None:
        try:
            from libs.ops.capability_graph import NODES
            acc: dict[str, set[str]] = defaultdict(set)
            for n in NODES:
                acc[n.module].update(n.reads)
            _GRAPH_READS = {k: tuple(sorted(v)) for k, v in acc.items()}
        except Exception:
            _GRAPH_READS = {}
    extra = [r for c in s.code_paths for r in _GRAPH_READS.get(c, ())]
    return tuple(dict.fromkeys([*s.inputs, *extra]))


def interfaces(specs: list[Any]) -> dict[str, Any]:
    by_owner: dict[str, dict[str, int]] = defaultdict(lambda: {"components": 0, "outputs": 0,
                                                               "inputs": 0})
    for s in specs:
        o = by_owner[str(s.owner or "UNDECLARED")]
        o["components"] += 1
        o["outputs"] += len(s.outputs)
        o["inputs"] += len(_inputs(s))
    return {"components": len(specs),
            "with_outputs": sum(1 for s in specs if s.outputs),
            "with_inputs": sum(1 for s in specs if _inputs(s)),
            "input_rule": "inputs = the registry's declared inputs plus the capability graph's "
                          "reads for the same module; a component declaring neither has its "
                          "inputs UNMEASURED, which is why STALE_BY_DESIGN is a floor",
            "with_consumers": sum(1 for s in specs if s.consumers),
            "by_owner": dict(sorted(by_owner.items(), key=lambda kv: -kv[1]["components"])[:40])}


def state_ownership(specs: list[Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    writers: dict[str, set[str]] = defaultdict(set)
    ids: dict[str, set[str]] = defaultdict(set)
    for s in specs:
        for o in s.outputs:
            writers[o].add(_primary_code(s))
            ids[o].add(s.component_id)
    owner = _graph_owner()
    findings = []
    for path, codes in sorted(writers.items()):
        if len(codes) > 1:
            first = owner.get(path) or sorted(ids[path])[0]
            findings.append({"class": "CONTESTED_STATE", "subject": path,
                             "parties": sorted(codes), "owner": first,
                             "resolution": RESOLUTION["CONTESTED_STATE"]})
    return {"paths": len(writers), "single_owner": sum(1 for c in writers.values()
                                                       if len(c) == 1),
            "contested": len(findings)}, findings


def timing(specs: list[Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cad: dict[str, int] = {}
    who: dict[str, str] = {}
    for s in specs:
        for o in s.outputs:
            if s.cadence_s and (o not in cad or s.cadence_s < cad[o]):
                cad[o], who[o] = int(s.cadence_s), s.component_id
    findings = []
    for s in specs:
        if not s.max_silence_s:
            continue
        for i in _inputs(s):
            if i in cad and cad[i] > int(s.max_silence_s):
                findings.append({"class": "STALE_BY_DESIGN", "subject": s.component_id,
                                 "parties": [who[i], s.component_id], "input": i,
                                 "producer_cadence_s": cad[i],
                                 "consumer_max_silence_s": int(s.max_silence_s),
                                 "resolution": RESOLUTION["STALE_BY_DESIGN"]})
    classes: dict[str, int] = defaultdict(int)
    for s in specs:
        c = s.cadence_s
        classes["UNMEASURED" if not c else "<=5m" if c <= 300 else "<=1h" if c <= 3600
                else "<=1d" if c <= 86400 else ">1d"] += 1
    return {"cadence_classes": dict(classes), "scheduled": sum(1 for s in specs if s.scheduled),
            "stale_by_design": len(findings)}, findings


def _dict_literal(src: str, name: str) -> dict[str, int]:
    m = re.search(rf"^{name}: dict\[str, int\] = \{{(.*?)^\}}", src, re.S | re.M)
    if not m:
        return {}
    return {k: int(v.replace("_", "")) for k, v in
            re.findall(r'^\s*"([\w-]+)":\s*([\d_]+)', m.group(1), re.M)}


def budgets(specs: list[Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        src = HOURLY.read_text("utf-8")
    except OSError:
        return {"status": "UNMEASURED"}, []
    base = _dict_literal(src, "LEG_BUDGET_SEC")
    floor = _dict_literal(src, "LEG_BUDGET_FLOOR_SEC")
    legs = set(re.findall(r'_costed\("([^"]+)"', src))
    findings = []
    for leg, f in sorted(floor.items()):
        if leg in base and base[leg] < f:
            findings.append({"class": "BUDGET_BELOW_FLOOR", "subject": leg,
                             "parties": [f"base {base[leg]}s", f"floor {f}s"],
                             "resolution": RESOLUTION["BUDGET_BELOW_FLOOR"]})
    for leg in sorted(set(base) - legs):
        findings.append({"class": "DEAD_BUDGET", "subject": leg, "parties": [f"{base[leg]}s"],
                         "resolution": RESOLUTION["DEAD_BUDGET"]})
    hourly = [s for s in specs if s.kind == "leg"]
    total = sum(int((s.resource_budget or {}).get("budget_s") or s.timeout_s or 0)
                for s in hourly)
    return {"legs": len(legs), "budgeted_legs": len(base), "floored_legs": len(floor),
            "sum_leg_budget_s": total,
            "note": "legs run on several plans and residents, so the sum is the hour's ceiling "
                    "of declared budget, not its wall time"}, findings


def contract_directions() -> list[dict[str, Any]]:
    try:
        legs = json.loads(CONTRACTS.read_text("utf-8")).get("legs") or {}
    except (OSError, ValueError):
        return []
    want: dict[tuple[str, str], dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for leg, c in legs.items():
        m = (c or {}).get("metric") or {}
        if m.get("organ") and m.get("metric") and m.get("better"):
            want[(str(m["organ"]), str(m["metric"]))][str(m["better"])].add(leg)
    out = []
    for (organ, metric), dirs in sorted(want.items()):
        if len(dirs) > 1:
            out.append({"class": "METRIC_DIRECTION", "subject": f"{organ} {metric}",
                        "parties": {d: sorted(v) for d, v in dirs.items()},
                        "resolution": RESOLUTION["METRIC_DIRECTION"]})
    return out


def failure_and_uncertainty(specs: list[Any]) -> dict[str, Any]:
    crit: dict[str, int] = defaultdict(int)
    for s in specs:
        crit[str(s.criticality)] += 1
    return {"by_criticality": dict(crit),
            "with_restart_action": sum(1 for s in specs if s.restart_action),
            "without_restart_action": sum(1 for s in specs if not s.restart_action),
            "with_max_silence": sum(1 for s in specs if s.max_silence_s),
            "max_silence_unmeasured": sum(1 for s in specs if not s.max_silence_s),
            "with_progress_metric": sum(1 for s in specs if s.progress_metric != "UNMEASURED"),
            "rule": "a component whose cadence is undeclared has an UNMEASURED max silence: "
                    "nothing may call it late, and nothing may call it on time"}


def build() -> dict[str, Any]:
    specs = _specs()
    from ops import components
    problems = components.registry().problems()
    iface = interfaces(specs)
    own, own_f = state_ownership(specs)
    tim, tim_f = timing(specs)
    bud, bud_f = budgets(specs)
    dirs = contract_directions()
    fail = failure_and_uncertainty(specs)
    reg_f = [{"class": "REGISTRY_PROBLEM", "subject": p.split(":", 1)[0], "parties": [p],
              "resolution": RESOLUTION["REGISTRY_PROBLEM"]} for p in problems]
    contradictions = own_f + tim_f + bud_f + dirs + reg_f
    by_class: dict[str, int] = defaultdict(int)
    for c in contradictions:
        by_class[c["class"]] += 1
    return {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "status": "MEASURED",
            "source": "desks/mt5/ops/components.registry() + hourly_cycle leg budgets + "
                      "docs/research/experiment_contracts.json + libs/ops/capability_graph",
            "interfaces": iface, "state_ownership": own, "timing": tim,
            "resource_budgets": bud, "failure_and_uncertainty": fail,
            "contradictions": {"n": len(contradictions), "by_class": dict(by_class),
                               "resolutions": RESOLUTION, "rows": contradictions}}


def render(doc: dict[str, Any]) -> str:
    c = doc["contradictions"]
    L = ["# Institution design (derived)", "",
         "> DERIVED by `scripts/build_institution_design.py --render` from the component "
         "registry, the hourly cycle's budgets, the experiment contracts and the capability "
         "graph. Never edit this file: change the code it reads and re-render. The hourly leg "
         "`institution_design` republishes the same content as "
         "`desks/mt5/reports/INSTITUTION_DESIGN.json` on the box.", "",
         f"Rendered from the tree at {doc['at']}.", "",
         "## Interfaces", "",
         f"{doc['interfaces']['components']} registered components; "
         f"{doc['interfaces']['with_outputs']} declare outputs, "
         f"{doc['interfaces']['with_inputs']} declare inputs, "
         f"{doc['interfaces']['with_consumers']} name a consumer. Each component's full "
         "contract (inputs, outputs, consumers, owner, schedule, restart action, budget) is its "
         "row in `desks/mt5/ops/components.py`.", "",
         "| owner | components | outputs | inputs |", "|---|---:|---:|---:|"]
    for k, v in list(doc["interfaces"]["by_owner"].items())[:25]:
        L.append(f"| `{k}` | {v['components']} | {v['outputs']} | {v['inputs']} |")
    t, o, b, f = (doc["timing"], doc["state_ownership"], doc["resource_budgets"],
                  doc["failure_and_uncertainty"])
    L += ["", "## Timing", "",
          f"{t['scheduled']} components on a clock. Cadence classes: "
          + ", ".join(f"{k} {v}" for k, v in sorted(t["cadence_classes"].items())) + ".", "",
          "## State ownership", "",
          f"{o['paths']} declared output paths; {o['single_owner']} have one owner and "
          f"{o['contested']} are contested (below).", "",
          "## Uncertainty", "", f"{f['rule']}. {f['max_silence_unmeasured']} components carry "
          f"an UNMEASURED max silence; {f['with_progress_metric']} declare a progress metric.",
          "", "## Failure handling", "",
          "Criticality: " + ", ".join(f"{k} {v}" for k, v in sorted(f["by_criticality"].items()))
          + f". {f['with_restart_action']} components declare a restart action, "
          f"{f['without_restart_action']} do not.", "",
          "## Resource budgets", "",
          f"{b.get('legs')} hourly legs, {b.get('budgeted_legs')} with an explicit budget and "
          f"{b.get('floored_legs')} with a floor; declared leg budgets sum to "
          f"{b.get('sum_leg_budget_s')} s ({b.get('note')}).", "",
          "## Contradictions and how each is resolved", "",
          f"{c['n']} contradictions: "
          + (", ".join(f"{k} {v}" for k, v in sorted(c["by_class"].items())) or "none") + ".",
          "", "| class | resolution |", "|---|---|"]
    for k, v in c["resolutions"].items():
        L.append(f"| {k} | {v} |")
    L += ["", "| class | subject | parties |", "|---|---|---|"]
    for r in c["rows"][:200]:
        parties = r["parties"]
        ptxt = (json.dumps(parties) if isinstance(parties, dict) else ", ".join(parties))[:180]
        L.append(f"| {r['class']} | `{str(r['subject'])[:90]}` | {ptxt.replace('|', '/')} |")
    if c["n"] > 200:
        L.append(f"| ... | {c['n'] - 200} more in INSTITUTION_DESIGN.json | |")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--render", action="store_true", help="also rewrite " + str(DOC))
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = build()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    if a.render:
        DOC.write_text(render(doc), "utf-8")
    c = doc["contradictions"]
    print(f"institution design: {doc['interfaces']['components']} components; "
          f"{c['n']} contradictions {c['by_class']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
