"""THE SELF-REPAIR REGISTRY: four parts per class, one clock, and a manual count that only falls.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT / "desks" / "mt5" / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import self_repair_registry as reg  # noqa: E402

from scripts import check_self_repair as fence  # noqa: E402


def test_every_declared_class_names_a_detector_and_a_fence_that_exist() -> None:
    assert len(reg.CLASSES) >= 12
    for c in reg.CLASSES:
        assert (ROOT / c.detector).is_file(), f"{c.key}: detector {c.detector} is not in the tree"
        assert (ROOT / c.fence).is_file(), f"{c.key}: fence {c.fence} is not in the tree"
        assert c.cost.strip() and c.title.strip(), c.key
        assert c.repair.strip() or c.owner != "department:meta", (
            f"{c.key} has no repair and no other owner: a class named and abandoned")


def test_the_buckets_are_exhaustive_and_never_blank(tmp_path: Path) -> None:
    doc = reg.measure(tmp_path)
    assert doc["classes"] == len(reg.CLASSES)
    assert sum(doc["census"].values()) == doc["classes"]
    for r in doc["rows"]:
        assert r["bucket"] in reg.BUCKETS and r["why"].strip()
    # an empty tree has no detector artifacts at all: every class is found by hand, not "clean"
    assert doc["census"]["AUTOMATED"] == 0
    assert doc["census"]["MANUAL"] == doc["classes"]


def test_a_stopped_detector_is_never_a_clean_class(tmp_path: Path) -> None:
    c = reg.CLASSES[0]
    art = tmp_path / c.artifact
    art.parent.mkdir(parents=True, exist_ok=True)
    art.write_text(json.dumps({"n": 3}), encoding="utf-8")
    (tmp_path / c.detector).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / c.detector).write_text("x", encoding="utf-8")
    (tmp_path / c.fence).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / c.fence).write_text("x", encoding="utf-8")
    fresh = reg.judge(c, tmp_path)
    assert fresh["bucket"] == "AUTOMATED" and fresh["found"] == {"n": 3}
    stale = reg.judge(c, tmp_path, now=time.time() + c.window_s + 60)
    assert stale["bucket"] == reg.UNMEASURED and "stopped detector" in stale["why"]


def test_the_manual_count_ratchets_down_only(tmp_path: Path) -> None:
    (tmp_path / "docs" / "research").mkdir(parents=True)
    (tmp_path / "docs" / "research" / "self_repair_floor.json").write_text(
        json.dumps({"manual": 2}), encoding="utf-8")
    v = fence.measure(tmp_path)
    assert v["floor_manual"] == 2 and v["manual"] == len(reg.CLASSES)
    assert any("manual count rose" in f for f in v["failures"])


def test_the_registry_is_wired_to_a_clock_a_layer_and_the_law_gate() -> None:
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["self_repair"] == "meta"
    src = (ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '_costed("self_repair"' in src and '"self_repair": slf' in src
    gate = (ROOT / "scripts" / "run_law_gate.py").read_text(encoding="utf-8")
    assert "check_self_repair.py" in gate
