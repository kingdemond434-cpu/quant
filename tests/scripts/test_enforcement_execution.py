from __future__ import annotations

from pathlib import Path

from scripts import check_enforcement_execution as execution


def test_citations_resolve_without_laundering_suffixes() -> None:
    assert execution._strip_citation("libs/risk/gate.py:RiskGate") == "libs/risk/gate.py"
    assert execution._strip_citation("run_deadman_switch.py (Tier-3)") == ("run_deadman_switch.py")

    kind, path = execution._resolve("tests/ops/test_lawful.py")
    assert kind == "test"
    assert path is not None and path.is_file()

    kind, path = execution._resolve("check_production")
    assert kind == "fence"
    assert path is not None and path.name == "max_audit.py"


def test_public_symbols_ignore_private_and_keep_constants(tmp_path: Path) -> None:
    module = tmp_path / "module.py"
    module.write_text(
        "PUBLIC = 1\n_private_constant = 2\ndef visible(): pass\n"
        "def _hidden(): pass\nclass Exposed: pass\n",
        encoding="utf-8",
    )
    assert execution._public_symbols(module) == {"PUBLIC", "visible", "Exposed"}


def test_registered_fence_requires_definition_and_a_caller() -> None:
    assert execution._fence_registered("check_one", "def check_one(): pass\n") is False
    assert (
        execution._fence_registered("check_one", "def check_one(): pass\nCHECKS = [check_one]\n")
        is True
    )
    assert execution._fence_registered("missing", "CHECKS = [missing]\n") is False


def test_repository_enforcement_map_is_executable_and_portable() -> None:
    report = execution.evaluate()

    assert report["status"] == "OK"
    assert report["broken"] == []
    assert report["laws_unenforced"] == []
    assert report["laws_weakened"] == []
    assert report["manual"] == [
        {
            "path": "scripts/deep_review.py",
            "laws": ["L1.7"],
            "reason": execution._MANUAL["scripts/deep_review.py"],
        }
    ]
