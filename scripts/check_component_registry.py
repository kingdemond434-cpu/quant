#!/usr/bin/env python3
"""THE BIRTH FENCE FOR EXECUTABLES: nothing runs on this desk without a ComponentSpec.

    DESIRED STATE - OBSERVED STATE = RECONCILIATION WORK

The reconciler can only reconcile against a desired state that EXISTS. An executable with no spec
is invisible to it: nobody has said when it must run, what it owns, who reads that, how long it
may be silent, or what repairs it -- so when it stops, nothing notices, and that is the shape of
every operational outage this desk has had. 293 unwired organs were counted in one morning; the
audit that found them had to be written by hand each time, after the fact.

WHAT THIS CHECKS, all repo-only so it means the same in CI, a fresh clone and on the box:

  (a) EVERY executable python file under desks/mt5/{research,scripts,moat,ops}, scripts/ and
      libs/ops carries a ComponentSpec. Coverage below 100% is exit 2. `desks/mt5/ops/components.py`
      derives specs from the hourly legs, the daily steps, the box task manifest, the residents,
      the VPS timers and the federation roster, and DECLARES the rest by name -- so this can only
      fail if the walk finds a file the registry's own discovery tier did not, which means the
      registry is broken rather than merely behind.

  (b) THE REGISTRY DOES NOT LIE ABOUT ITSELF: no spec names a code path that does not exist, no
      required component lacks a schedule, no max_silence is shorter than its own cadence, no id
      is duplicated. Each of those is a spec that would make the reconciler certify a fiction.

  (c) THE COUNT OF EXECUTABLES WITH NO CLOCK IS RATCHETED DOWN. This is the honest half. 684 files
      in this tree have a `main()` and no clock anywhere in the repo: putting them all on one is
      not this fence's job and inventing cadences for them would be worse than leaving them off.
      So the number is MEASURED, published, and may only fall -- a new executable must arrive with
      a clock, or the fence goes red.

  (d) NO SECOND REGISTRY. `clock_fixer.RESIDENTS`, `moat_swarms.TASK_NAMES` and
      `forests.FOREST_TASKS` must agree with the specs. Four registries of one machine, each true
      about a different subset, is what this whole control plane replaces.

Exit: 2 on (a), (b) or a ratchet breach; 1 on (d) drift; 0 clean.

    python scripts/check_component_registry.py [--json]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT = ROOT / "desks" / "mt5" / "reports" / "COMPONENT_REGISTRY.json"

#: RATCHET: executables with a `main()` and no clock in this repository. It may FALL, never rise.
#: 684 on 2026-09-17, 700 as the ratchet, 200 on 2026-09-22 after nine builders wired their own
#: organs, and ONE on 2026-09-23 after the wiring sweep (principal: "100 percent of everything
#: built always must be used never forgotten"): 85 dated one-shots, demo executors and seat-only
#: tools retired to `_retired/` with a row in `docs/research/retirements.jsonl`, 82 fences,
#: standing fixers and region organs rostered on the two standing batteries
#: (the batteries module under desks/mt5/research, hourly legs `fence_battery` and
#: `organ_battery`), and two
#: classifier blind spots closed -- the country packs `forest_runner` imports by f-string, and
#: the 85 SYSTEMD units `ops/crontab.manifest` declares beside its cron lines.
#:
#: THE ONE THAT REMAINS is the arm-and-pass tool under desks/mt5/scripts: it restores the money
#: path to HEAD and runs one gateway pass, an operator recovery tool the new-box migration
#: runbook tells a human to run. No clock may arm the money path unattended, so it stays
#: unclocked ON PURPOSE and the ratchet is exactly one, so the next unclocked executable turns
#: this fence red. (Its name is spelled without a path here deliberately: `scripts_named_in`
#: reads path literals out of any file a clock reaches, so naming it in full would have made
#: THIS COMMENT its clock -- a fence laundering its own worklist into a claim of wiring.)
#:
#: Three executables landed unwired DURING this sweep (the implementer organ and two seat/flow
#: fences) and were counted, named and handed back rather than rostered behind their authors:
#: their builders wired the first within the hour and the batteries took the two fences. That is
#: the ratchet working -- a new executable arrives with a clock, or this fence goes red.
#:
#: THE VALUE IS TWO, not one, and the second slot is deliberate: a dozen builders work this tree
#: at once and an organ can land minutes before the leg that clocks it, so a ratchet of exactly
#: one makes the law gate red for whoever runs it in that gap. One slot of headroom keeps the
#: fence honest and usable; a THIRD unclocked executable turns it red, which is the point.
MAX_UNCLOCKED = 2


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, mod)
    spec.loader.exec_module(mod)
    return mod


def _residents_drift(comp: Any) -> list[str]:
    """`clock_fixer.RESIDENTS` must BE the specs, not a copy of them."""
    out: list[str] = []
    path = ROOT / "desks" / "mt5" / "research" / "clock_fixer.py"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [f"{path} unreadable"]
    if re.search(r"^RESIDENTS:\s*dict\[str,\s*tuple\[str,\s*str,\s*int\]\]\s*=\s*\{", text, re.M):
        out.append("clock_fixer.RESIDENTS is still a hand-written dict literal; it must be "
                   "derived from desks/mt5/ops/components.residents()")
    try:
        mod = _load(path, "_cf_for_drift")
        live = dict(getattr(mod, "RESIDENTS", {}) or {})
    except Exception as exc:                                    # pragma: no cover - import guard
        return [*out, f"clock_fixer import failed: {type(exc).__name__}: {exc}"]
    want = comp.residents()
    for stem in sorted(set(want) | set(live)):
        if stem not in live:
            out.append(f"clock_fixer.RESIDENTS is missing resident {stem}")
        elif stem not in want:
            out.append(f"clock_fixer.RESIDENTS holds {stem}, which no ComponentSpec declares")
        elif tuple(live[stem]) != tuple(want[stem]):
            out.append(f"{stem}: clock_fixer has {tuple(live[stem])}, specs say {want[stem]}")
    return out


def _task_registry_drift(comp: Any) -> list[str]:
    """`moat_swarms.TASK_NAMES` and `forests.FOREST_TASKS` must be covered by the specs."""
    out: list[str] = []
    reg = comp.registry(ROOT)
    scheduled = {s.schedule for s in reg.all() if s.scheduled}
    for swarm, task in comp.swarm_tasks().items():
        if task not in scheduled:
            out.append(f"moat_swarms.TASK_NAMES[{swarm!r}] = {task} has no ComponentSpec")
    forests = comp.forests_module()
    if forests is not None:
        for fid, task in getattr(forests, "FOREST_TASKS", {}).items():
            if fid in getattr(forests, "RIDES", {}):
                continue
            if task not in scheduled:
                out.append(f"forests.FOREST_TASKS[{fid!r}] = {task} has no ComponentSpec")
    return out


def _unlanded_retirements(unclocked: list[str]) -> list[str]:
    """Which unclocked executables are RETIRED organs whose removal never landed on this host.

    THE 2 -> 88 STEP OF 2026-09-23, AND WHY A BARE NUMBER COULD NOT EXPLAIN IT. The wiring sweep
    retired 92 dated one-shots and demo executors with `git mv <path> _retired/<path>` and a row
    in docs/research/retirements.jsonl. The build box carries the result: only the `_retired/`
    copy, 3 unclocked. Origin -- and therefore the trading box that adopts it -- carries BOTH
    copies, because the shipping path between them moves file CONTENT and not file REMOVAL: the
    add of `_retired/x.py` lands, the delete of `x.py` never does. So 87 organs that were retired
    are still sitting at their original paths on that host, each still carrying a `main()` and
    still, correctly, counted here as an executable nobody clocks.

    This does not except them and does not move the ratchet: an unclocked executable is unclocked
    wherever it sits, and the remedy is to land the removals, never to widen the fence. It names
    them, because "88 with no clock" and "87 retirements whose delete half never shipped" send an
    operator to two different places, and only one of them is the defect.
    """
    ledger = ROOT / "docs" / "research" / "retirements.jsonl"
    retired: set[str] = set()
    try:
        for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            # Only where the replacement copy is actually present: a retirement row whose
            # `_retired/` copy never arrived either is a plain missing file, not a duplicate.
            if (isinstance(row, dict) and row.get("path") and row.get("retired_to")
                    and (ROOT / str(row["retired_to"])).exists()):
                retired.add(str(row["path"]).replace("\\", "/"))
    except OSError:
        return []
    return sorted(set(unclocked) & retired)


def measure() -> dict[str, Any]:
    comp = _load(ROOT / "desks" / "mt5" / "ops" / "components.py", "_cp_components_fence")
    census = comp.census(ROOT)
    reg = comp.registry(ROOT)
    unclaimed = list(census.get("executables_unclaimed") or [])
    problems: list[str] = list(census.get("problems") or [])
    unclocked = int(census.get("executables_without_clock") or 0)
    drift = _residents_drift(comp) + _task_registry_drift(comp)

    fatal: list[str] = []
    if unclaimed:
        fatal.append(f"{len(unclaimed)} executable(s) carry no ComponentSpec: {unclaimed[:8]}")
    fatal += problems
    unlanded = _unlanded_retirements(list(census.get("unclocked") or []))
    if unclocked > MAX_UNCLOCKED:
        fatal.append(f"executables with no clock rose to {unclocked} (ratchet "
                     f"{MAX_UNCLOCKED}): a new executable must arrive with a clock")
        if unlanded:
            fatal.append(f"{len(unlanded)} of those {unclocked} are RETIRED organs still present "
                         f"at their original path ({unlanded[:3]}...): docs/research/"
                         f"retirements.jsonl records them moved to _retired/, and the _retired/ "
                         f"copy is here, so the delete half of the move never landed on this "
                         f"host. Land the removals -- do not clock them and do not raise the "
                         f"ratchet")

    return {
        "at": __import__("datetime").datetime.now(
            tz=__import__("datetime").UTC).isoformat(timespec="seconds"),
        "components": len(reg),
        "executables": census.get("executables"),
        "coverage": census.get("coverage"),
        "scheduled": census.get("scheduled"),
        "unscheduled": census.get("unscheduled"),
        "executables_without_clock": unclocked,
        "unclocked_ratchet": MAX_UNCLOCKED,
        "unclocked_unlanded_retirements": unlanded,
        "by_kind": census.get("by_kind"),
        "registry_problems": problems,
        "second_registry_drift": drift,
        "fatal": fatal,
        # THE FRESHNESS EXPECTATION, PUBLISHED (principal 2026-09-22: nothing stale, and a stale
        # artifact surfaces as a NAMED defect with the organ that owns it). One row per scheduled
        # component: the clock that fires it, the cadence it claims, the silence after which that
        # silence is a fault, and the artifact class its lease is derived from. An anti-staleness
        # prover reads THIS -- it never has to re-derive a cadence, and an organ whose cadence is
        # UNMEASURED says so by name rather than defaulting to "fresh".
        "freshness": sorted(
            ({"component_id": s.component_id, "kind": s.kind, "schedule": s.schedule,
              "code_paths": list(s.code_paths), "cadence_s": s.cadence_s,
              "max_silence_s": s.max_silence_s, "artifact_class": s.artifact_class,
              "outputs": list(s.outputs), "consumers": list(s.consumers),
              "criticality": s.criticality, "owner": s.owner}
             for s in reg.all() if s.scheduled),
            key=lambda r: str(r["component_id"])),
        "unclocked": list(census.get("unclocked") or []),
        "ok": not fatal and not drift,
        "rule": ("every executable carries a ComponentSpec; the registry may not name a file that "
                 "does not exist nor a required component without a schedule; the count of "
                 "executables with no clock may only fall; and no second registry of the same "
                 "machine may disagree with the specs"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    doc = measure()
    try:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    except OSError:
        pass
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        print(f"component registry: {doc['components']} spec(s) over {doc['executables']} "
              f"executable(s); coverage {doc['coverage']}; "
              f"{doc['executables_without_clock']} with no clock (ratchet "
              f"{doc['unclocked_ratchet']}); {len(doc['registry_problems'])} registry problem(s), "
              f"{len(doc['second_registry_drift'])} drift row(s)")
        for f in doc["fatal"][:10]:
            print("   FATAL:", f)
        for d in doc["second_registry_drift"][:10]:
            print("   DRIFT:", d)
    if doc["fatal"]:
        return 2
    if doc["second_registry_drift"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
