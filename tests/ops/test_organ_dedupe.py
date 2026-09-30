"""ONE ORGAN, ONE ID: a manifest task that keeps a modelled organ alive is that organ.

The gateway resident was deduplicated first (PR #171). The same double entry held for the control
plane and for every department, forest and moat-swarm resident; these tests find every such pair
from the specs themselves, so a new resident whose task is added without its TASK_CANONICAL line
fails here instead of being counted twice.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from libs.ops.control_plane import edges

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"


def _components():
    name = "_quant_organ_dedupe_components"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, DESK / "ops" / "components.py")
    assert spec and spec.loader
    c = importlib.util.module_from_spec(spec)
    sys.modules[name] = c   # dataclasses resolve their module by name
    spec.loader.exec_module(c)
    return c


def test_no_resident_or_component_is_registered_twice() -> None:
    gaps = _components().task_canonical_gaps()
    assert gaps["unlisted"] == [], (
        "manifest tasks registered beside the organ they keep alive -- add each to "
        f"components.TASK_CANONICAL: {gaps['unlisted']}")
    assert gaps["dangling"] == [], f"TASK_CANONICAL names no organ: {gaps['dangling']}"
    assert gaps["unclaimed"] == [], f"dedupe would orphan a script: {gaps['unclaimed']}"


def test_the_detector_catches_a_missing_entry(monkeypatch) -> None:
    c = _components()
    trimmed = {k: v for k, v in c.TASK_CANONICAL.items() if k != "MT5-Dept-Intel"}
    monkeypatch.setattr(c, "TASK_CANONICAL", trimmed)
    assert c.task_canonical_gaps()["unlisted"] == ["MT5-Dept-Intel -> resident:dept_intel"]
    assert any(s.component_id == "task:MT5-Dept-Intel" for s in c.manifest_task_specs())


def test_the_detector_catches_a_dangling_entry(monkeypatch) -> None:
    c = _components()
    monkeypatch.setattr(c, "TASK_CANONICAL", {**c.TASK_CANONICAL, "MT5-Hourly": "resident:nope"})
    gaps = c.task_canonical_gaps()
    assert "MT5-Hourly -> resident:nope" in gaps["dangling"]
    assert "MT5-Hourly -> resident:dept_discovery" in gaps["unlisted"]


def test_every_family_is_deduplicated() -> None:
    c = _components()
    task_ids = {s.component_id for s in c.manifest_task_specs()}
    organs = {s.component_id: s for s in (*c.explicit_specs(), *c.resident_specs())}
    for task, cid in c.TASK_CANONICAL.items():
        assert f"task:{task}" not in task_ids
        assert organs[cid].schedule == task
        assert organs[cid].restart_action == f"restart:task:{task}"
    families = {cid.split(":", 1)[1].split("_", 1)[0] for cid in c.TASK_CANONICAL.values()}
    assert {"dept", "moat", "gateway", "control"} <= families
    assert c.TASK_CANONICAL["MT5-ClockFixer"] == "component:control_plane"
    assert c.TASK_CANONICAL["MT5-Hourly"] == "resident:dept_discovery"
    # the canonical control-plane organ's entrypoint is the script its task runs, with args it takes
    cp = organs["component:control_plane"]
    assert cp.code_paths[0] == "desks/mt5/research/clock_fixer.py"
    assert "--once" not in cp.production_args


def test_the_scheduler_renders_the_same_manifest_rows() -> None:
    from libs.ops.control_plane import scheduler_gen
    c = _components()
    desired = scheduler_gen.desired_rows(c.build_registry())
    have = scheduler_gen.manifest_rows()
    for task, cid in c.TASK_CANONICAL.items():
        assert desired[task]["component_id"] == cid
        assert desired[task]["runs"] in {r.get("runs") for r in have[task]}


def test_edges_name_the_canonical_organ_not_the_task() -> None:
    c = _components()
    for e in edges.REQUIRED_EDGES:
        for end in (e.producer, e.consumer):
            if end.startswith("task:"):
                assert end.split(":", 1)[1] not in c.TASK_CANONICAL, end
    assert edges.edges_for(consumer="component:control_plane")[0].producer == "leg:control_plane"
    assert not edges.edges_for(consumer="task:MT5-ClockFixer")
