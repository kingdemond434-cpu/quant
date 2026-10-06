"""An organ's declared chain must distinguish physical evidence from a claim."""
import json
import os
from types import SimpleNamespace

import pytest

from libs.ops import organ_census as oc


def write(root, name, body, at=100000):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    os.utime(path, (at, at))
    return path


def test_all_native_rosters_join_one_declared_chain(tmp_path):
    code = "scripts/miner.py"
    artifact = "data/out.json"
    write(tmp_path, code, "pass")
    write(tmp_path, artifact, json.dumps({"cells": ["x" * 1500]}))
    write(tmp_path, "data/input/seat/bars.csv", "bars\n" * 400)
    node = SimpleNamespace(name="miner", module=code, writes=[artifact],
                           reads=["data/input"], freshness_s={"bars": 86400}, authority=[])
    feeder = {
        "producer_census": {"rows": [None, {"producer": "miner", "kind": "miner",
            "organ": code, "production_paths": [code, artifact], "clock": "hourly"}]},
        "productivity": {"producers": [None, {"producer": "miner", "unique_cells": 40,
            "cells_reached_judge": 30, "cells_judged": 25, "compute_hours": 2}]},
        "component_registry": {"components": 1, "freshness": [{"component_id": "miner",
            "code_paths": [code], "outputs": [artifact], "inputs": ["data/input"],
            "schedule": "hourly"}], "unclocked": [None, {}]},
        "capability_nodes": [SimpleNamespace(name=""), node],
        "dead_architecture": {"organs": {code: {"verdict": "LIVE", "artifacts": [artifact],
            "n_consumers": 1}, "ignored": None}},
        "attribution": {"certificates": {"by_producer": {"miner": 2}}},
        "compute_economics": {"by_department": {"miner": {"survivors_per_wall_hour": 1},
                                                    "invalid": None}},
    }
    result = oc.census(root=tmp_path, feeders=feeder, now=100100, mirror=False)
    assert result["reconciliation"]["organs_in_all_three_censuses"] == 1
    row = result["rows"][0]
    assert row["organ"] == "miner" and all(v == oc.REAL for v in row["chain"].values())
    assert row["first_break"] is None
    mirrored = oc.census(root=tmp_path, feeders=feeder, now=100100, mirror=True)
    assert mirrored["rows"][0]["chain"]["input"] == oc.UNMEASURED
    assert mirrored["rows"][0]["chain"]["artifact"] == oc.UNMEASURED


@pytest.mark.parametrize("mode", ["missing", "empty", "stale", "real"])
def test_input_link_uses_owned_nested_file_evidence(tmp_path, mode):
    organ = oc.Organ("miner", inputs={"data/in"})
    if mode != "missing":
        write(tmp_path, "data/in/seat/receipt.json", "{}" if mode == "empty" else "x" * 2000,
              at=100 if mode == "stale" else 100000)
    result = oc.chain_for(organ, root=tmp_path, now=100100, mirror=False)
    assert result["input"]["verdict"] == (oc.REAL if mode == "real" else oc.BROKEN)
    assert result["code"]["verdict"] == oc.UNMEASURED


@pytest.mark.parametrize("mode", ["missing", "fresh", "stale"])
def test_liveness_is_not_a_payload(tmp_path, mode):
    organ = oc.Organ("resident", artifacts={"data/locks/resident.lock"})
    if mode != "missing":
        write(tmp_path, "data/locks/resident.lock", "1", at=100 if mode == "stale" else 100000)
    result = oc.chain_for(organ, root=tmp_path, now=100100, mirror=False)
    expected = oc.UNMEASURED if mode == "fresh" else oc.BROKEN
    assert result["artifact"]["verdict"] == expected
    assert result["artifact"]["liveness_only"]


def test_newer_empty_receipt_does_not_hide_older_payload(tmp_path):
    write(tmp_path, "data/out/seat/payload.json", "x" * 2000, 100000)
    write(tmp_path, "data/out/latest.json", "{}", 100100)
    organ = oc.Organ("miner", artifacts={"data/out"})
    chain = oc.chain_for(organ, root=tmp_path, now=100200, mirror=False)
    assert chain["artifact"]["verdict"] == oc.REAL
    newest, payload, count = oc._newest_payload(tmp_path, organ.artifacts)
    assert newest[1].endswith("latest.json") and payload[1].endswith("payload.json")
    assert count == 1
    assert oc._newest(tmp_path, organ.artifacts)[1].endswith("latest.json")


def test_private_capability_graph_imports_dataclass_without_real_roster_leak(tmp_path):
    assert oc.capability_nodes(tmp_path) == []
    write(tmp_path, "libs/ops/capability_graph.py", (
        "from dataclasses import dataclass\n@dataclass\nclass Node:\n    name: str\n"
        "NODES=[Node('owned')]\n"))
    nodes = oc.capability_nodes(tmp_path)
    assert [n.name for n in nodes] == ["owned"]


def test_sandbox_and_component_declarations_keep_unmeasured_counts():
    assert oc.claims_from_component_registry({"components": 12}) == []
    claims = oc.claims_from_sandbox_roster({"systems": [None, {},
        {"system_id": "one", "candidates": 12, "runs": 2},
        {"system_id": "two", "candidates": "unknown"}]})
    assert claims[0].detail["unique_cells"] == 12
    assert claims[1].detail["unique_cells"] is None
    assert oc.claims_from_sandbox({"reasons": {"one": {"why": "missing"}, "two": "not run"}})
