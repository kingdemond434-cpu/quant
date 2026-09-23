"""THE DESK'S OWN SANDBOXED RESEARCH CELLS -- the "stealable" mechanisms of the federation's
best systems, REBUILT in the desk's code so they run on this box today with numpy alone and
prefer the upstream engine (through its adapter) whenever it is installed.

A cell is not a third-party system: it is desk code, licensed by the desk, run in-process by
`desks/mt5/research/sandbox_runner.py` over the same READ-ONLY ResearchBundle every adapter
gets. It shares the adapters' exit -- an ExternalResearchPacket, candidates and representations
with provenance and a real trial count -- so a cell can donate a hypothesis and never a verdict
(LAWS 5h). Its `system_id` carries `adapters.CELL_PREFIX` and its commit is the desk tree's
HEAD, which is how the registry tells a rebuilt mechanism from an upstream run.

THE CONTRACT. Each module exposes `CELL` (its id), `CAPABILITY_FAMILY`, `UPSTREAM` (the
adapter systems it prefers when installed), `FALLBACK` (what runs when they are not) and
`run(bundle, ctx) -> ExternalResearchPacket`. `run_cell` guards the call: a cell that raises
leaves an UNMEASURED packet naming the failure, never a dead hour.
"""
from __future__ import annotations

import importlib
import traceback
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

#: Cell id -> module name (relative to this package). Order is the runner's default order.
CELLS: tuple[str, ...] = ("path_signature_lab", "conformal_calibration", "coevolution_cell",
                          "edgar_transmission", "rl_execution_challenger")


@dataclass(frozen=True)
class CellContext:
    """What a cell may read besides the bundle: desk paths (read-only by convention), whether
    network egress is permitted for THIS pass, the compute budget and the seed."""

    desk: Path
    budget_s: int = 300
    seed: int = 0
    network_allowed: bool = False
    dry_run: bool = False
    #: Whether a cell may also run the desk's heavier reference engine (feature store, model
    #: zoo) beside its numpy loop; off in tests and dry runs.
    reference_engines: bool = False

    @property
    def data(self) -> Path:
        return self.desk / "data"

    @property
    def reports(self) -> Path:
        return self.desk / "reports"


def system_id(cell: str) -> str:
    return f"{A.CELL_PREFIX}{cell}"


def load_cell(cell: str) -> ModuleType:
    if cell not in CELLS:
        raise KeyError(f"{cell!r} is not a registered cell: {CELLS}")
    return importlib.import_module(f"{__name__}.{cell}")


def describe(module: ModuleType) -> dict[str, Any]:
    cell = str(getattr(module, "CELL", ""))
    upstream = tuple(getattr(module, "UPSTREAM", ()))
    return {"name": system_id(cell), "cell": cell,
            "licence": "desk (own code; mechanism rebuilt from " + (", ".join(upstream)
                                                                    or "the desk's own method")
            + ")", "capability_family": str(getattr(module, "CAPABILITY_FAMILY", "")),
            "upstream": list(upstream), "fallback": str(getattr(module, "FALLBACK", "")),
            "upstream_available": [u for u in upstream if (A.SPECS.get(u) is not None
                                                          and A.library(A.SPECS[u].module)
                                                          is not None)],
            "run": getattr(module, "run", None)}


def run_cell(cell: str, bundle: A.ResearchBundle, ctx: CellContext) -> ExternalResearchPacket:
    """Run one cell, guarded: an exception becomes an UNMEASURED packet with the failure named
    (the runner records RUN_FAILED and the hour keeps its other cells)."""
    sid = system_id(cell)
    try:
        module = load_cell(cell)
        result = module.run(bundle, ctx)
        if not isinstance(result, ExternalResearchPacket):
            return A.unmeasured(sid, bundle, f"cell returned {type(result).__name__}, not a "
                                             "packet")
        return result
    except Exception:
        tail = traceback.format_exc().strip().splitlines()[-3:]
        return A.unmeasured(sid, bundle, "cell raised: " + " | ".join(tail)[:600])
