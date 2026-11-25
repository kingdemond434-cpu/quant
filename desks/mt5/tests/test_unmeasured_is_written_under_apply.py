"""L1.28a: UNMEASURED is a real answer. Under --apply the six frontier organs must WRITE the
UNMEASURED document over the previous artifact, never return 0 and let the old one age silently."""
from __future__ import annotations

import importlib
import json
import tempfile
from pathlib import Path

MODULES = (
    "capacity_frontier", "joint_evolution", "market_ecology",
    "market_posteriors", "representation_discovery", "causal_discovery",
)


def _load(name: str):
    try:
        return importlib.import_module(f"research.{name}")
    except ImportError:
        return importlib.import_module(f"mt5desk.research.{name}")


def test_unmeasured_doc_replaces_the_previous_artifact_under_apply() -> None:
    for name in MODULES:
        mod = _load(name)
        old_build, old_out = mod.build, mod.OUT
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "reports" / "X.json"
            out.parent.mkdir()
            out.write_text(json.dumps({"status": "OK", "stale": True}), encoding="utf-8")
            mod.OUT = out
            mod.build = lambda *a, **k: {"status": "UNMEASURED", "why": "test: no data",
                                         "at": "2026-11-25T00:00:00Z"}
            try:
                assert mod.main([]) == 0, name
                assert json.loads(out.read_text("utf-8")).get("stale") is True, name  # no --apply
                assert mod.main(["--apply"]) == 0, name
                doc = json.loads(out.read_text("utf-8"))
            finally:
                mod.build, mod.OUT = old_build, old_out
            assert doc["status"] == "UNMEASURED" and doc["why"] == "test: no data", name
            assert "stale" not in doc, name
