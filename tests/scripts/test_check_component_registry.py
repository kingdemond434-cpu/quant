from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _module():
    path = ROOT / "scripts" / "check_component_registry.py"
    spec = importlib.util.spec_from_file_location("component_registry_acceptance", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_component_registry_measures_real_paths_and_has_no_drift() -> None:
    doc = _module().measure()
    assert doc["coverage"] == 1.0
    assert doc["registry_problems"] == []
    assert doc["second_registry_drift"] == []
    assert doc["ok"] is True
