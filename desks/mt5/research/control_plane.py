"""THE CONTROL PLANE ORGAN -- one reconciliation pass over the whole desk.

    DESIRED STATE - OBSERVED STATE = RECONCILIATION WORK

Two clocks run this file and they do different jobs:

    hourly leg `control_plane`   --once --budget-s 600            OBSERVE and report
    MT5-ClockFixer (15 minutes)  --once --apply --budget-s 600    OBSERVE, plan and REPAIR

The observe pass never touches the box. The apply pass runs the actuators the plan names and
proves each postcondition by observation before recording REPAIRED -- a return code of 0 is never
proof (`libs/ops/control_plane/actuators.py`).

It publishes `desks/mt5/reports/CONTROL_PLANE.json`: the twelve invariants, the per-component
states, the plan, the repairs with their proofs, the published detection+repair SLAs, and the one
top-level bit DESK_CLOSED_AND_HEALTHY with the exact first broken invariant underneath.

EXIT CODES ARE FAIL-CLOSED WHERE IT COSTS SOMETHING. A failed REQUIRED repair exits non-zero, so
the fifteen-minute task cannot report success over a repair that did not take. An observe pass
with red invariants exits 0 by default -- its job is to MEASURE, and a measurement organ that
fails the cycle every hour is an organ somebody removes from the cycle -- and `--strict` is there
for the caller that wants the verdict as an exit code.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.ops.control_plane import reconciler as rc  # noqa: E402
from libs.ops.control_plane import watermarks as wm  # noqa: E402

REPORT = DESK / "reports" / "CONTROL_PLANE.json"


def _registry():  # type: ignore[no-untyped-def]
    import importlib.util
    path = DESK / "ops" / "components.py"
    spec = importlib.util.spec_from_file_location("_cp_components_organ", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load the component registry from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(apply: bool = False, budget_s: float = 600.0, epoch: str | None = None,
        write: bool = True) -> dict:
    comp = _registry()
    reg = comp.registry(ROOT)
    census = comp.census(ROOT)
    doc = rc.reconcile(registry=reg, root=ROOT, apply=apply, budget_s=budget_s, epoch=epoch,
                       census=census)
    if write:
        env = rc.write(doc, REPORT, ROOT)
        doc = {**doc, "envelope": {"artifact_id": env.get("artifact_id"),
                                   "producer_run_id": env.get("producer_run_id")}}
        wm.progress("component:control_plane", "reconcile_passes",
                    int((wm.read("component:control_plane") or {}).get("value") or 0) + 1,
                    run_id=str(env.get("producer_run_id")), epoch_id=str(doc.get("epoch_id")))
        wm.progress("leg:control_plane", "reconcile_passes",
                    int((wm.read("leg:control_plane") or {}).get("value") or 0) + 1,
                    run_id=str(env.get("producer_run_id")), epoch_id=str(doc.get("epoch_id")))
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode there is)")
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--apply", action="store_true", help="run the planned repairs")
    ap.add_argument("--dry-run", action="store_true", help="observe only; overrides --apply")
    ap.add_argument("--epoch", default=None, help="certify this controller epoch")
    ap.add_argument("--strict", action="store_true",
                    help="exit 2 when DESK_CLOSED_AND_HEALTHY is false")
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    apply = bool(a.apply and not a.dry_run)
    doc = run(apply=apply, budget_s=a.budget_s, epoch=a.epoch, write=not a.no_write)
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        broken = doc.get("first_broken_invariant")
        print(f"control plane [{doc['mode']}] {doc['at']} epoch={doc['epoch_id']}: "
              f"DESK_CLOSED_AND_HEALTHY={doc['DESK_CLOSED_AND_HEALTHY']} over "
              f"{doc['components']} component(s)")
        print("  states:", ", ".join(f"{k}={v}" for k, v in sorted(doc["states"].items())))
        for name in rc.INVARIANTS:
            inv = doc["invariants"][name]
            mark = "ok " if inv["ok"] is True else ("RED" if inv["ok"] is False else "UNM")
            print(f"  {mark} {name:<24} {str(inv['measured'])[:80]}")
            if inv["ok"] is not True and inv["why"]:
                print(f"      why: {inv['why'][:160]}")
        if broken:
            print(f"  first broken invariant: {broken['invariant']} -- "
                  f"{str(broken.get('why'))[:160]}")
        if doc["plan"]:
            print(f"  plan: {len(doc['plan'])} repair(s);"
                  f" applied {len(doc['repairs'])}")
        for r in doc["repairs"][:10]:
            print(f"    {r.get('component_id')}: {r.get('result')} -- {str(r.get('why'))[:100]}")
    failed = doc.get("failed_required_repairs") or []
    if failed:
        print(f"control plane: {len(failed)} REQUIRED repair(s) did not prove their "
              f"postcondition: {failed[:5]}", file=sys.stderr)
        return 1
    if a.strict and not doc.get("DESK_CLOSED_AND_HEALTHY"):
        return 2
    return 0


def now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


if __name__ == "__main__":
    raise SystemExit(main())
