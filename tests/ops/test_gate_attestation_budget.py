"""The gate verdict recorder must outlive its own bounded Git observations."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]


def test_attestation_record_budget_covers_three_bounded_git_reads() -> None:
    path = ROOT / "scripts" / "run_gate_attestation.py"
    spec = importlib.util.spec_from_file_location("run_gate_attestation", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.ATTEST_RECORD_TIMEOUT_S >= 3 * 60


def test_gate_collection_manifest_contains_only_tracked_pytest_patterns(
        monkeypatch, tmp_path) -> None:
    path = ROOT / "scripts" / "run_gate_attestation.py"
    spec = importlib.util.spec_from_file_location("run_gate_attestation_manifest", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "TEST_MANIFEST", tmp_path / "gate_tests.txt")
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        returncode=0,
        stdout="tests/test_alpha.py\nlibs/research/model.py\nresearch/placebo_test.py\n",
        stderr="",
    ))
    paths, error = module._tracked_python_paths()
    manifest, error = module._tracked_test_manifest(paths)
    assert error == "" and manifest == module.TEST_MANIFEST
    assert manifest.read_text("utf-8").splitlines() == ["tests/test_alpha.py"]


def test_ruff_population_uses_canonical_discovery_and_rejects_outside_paths(
        monkeypatch) -> None:
    path = ROOT / "scripts" / "run_gate_attestation.py"
    spec = importlib.util.spec_from_file_location("run_gate_attestation_ruff", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    inside = module.ROOT / "libs" / "alpha.py"
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        returncode=0, stdout=f"{inside}\n", stderr=""))
    paths, error = module._ruff_discovered_paths("python")
    assert error == ""
    assert paths == ["libs/alpha.py"]

    monkeypatch.setattr(module.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        returncode=0, stdout=f"{module.ROOT.parent / 'outside.py'}\n", stderr=""))
    paths, error = module._ruff_discovered_paths("python")
    assert paths == []
    assert "outside the release root" in error


def test_tracked_python_census_runs_once_for_many_untracked_files(monkeypatch, tmp_path) -> None:
    path = ROOT / "scripts" / "gate_attestation.py"
    spec = importlib.util.spec_from_file_location("gate_attestation", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    calls: list[tuple[str, ...]] = []

    def fake_git(*args: str) -> str:
        calls.append(args)
        if args == ("diff-files", "--name-status"):
            return ""
        if args == ("diff-index", "--cached", "--name-status", "HEAD"):
            return ""
        if args == ("ls-files", "*.py"):
            return "real_module.py\n"
        if args == ("rev-parse", "HEAD"):
            return "abc"
        if args[:3] == ("ls-tree", "-r", "--full-tree"):
            return "100644 blob deadbeef\treal_module.py"
        return ""

    monkeypatch.setattr(module, "_git", fake_git)
    monkeypatch.setattr(module, "OUT", tmp_path / "gate_attestation.json")
    payload = module.attest("fast", "pass")
    module.OUT.write_text(json.dumps(payload), encoding="utf-8")

    assert calls.count(("ls-files", "*.py")) == 1
    assert payload["tree_clean"] is True


def test_working_tree_census_does_not_request_all_untracked_state(monkeypatch) -> None:
    path = ROOT / "scripts" / "gate_attestation.py"
    spec = importlib.util.spec_from_file_location("gate_attestation_fast_census", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(module, "_git", lambda *args: calls.append(args) or "")
    module._working_tree_rows()
    assert ("diff-files", "--name-status") in calls
    assert ("diff-index", "--cached", "--name-status", "HEAD") in calls
    assert ("status", "--porcelain") not in calls
