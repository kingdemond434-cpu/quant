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
    # MANUAL is a decision on the record, never a default: every reported manual citation must
    # be registered in _MANUAL and carry its registered reason verbatim. The exact membership is
    # NOT pinned -- an entry legitimately leaves this list when a caller starts running it
    # (deep_review.py did exactly that: shell/CI runner ops/run_cro_ai.sh now executes it, and
    # the stale exact-list pin here read that improvement as a failure).
    manual_paths = {m["path"] for m in report["manual"]}
    assert manual_paths, "the on-the-record exemption mechanism must be exercised, not vestigial"
    assert manual_paths <= set(execution._MANUAL), (
        f"unregistered MANUAL citation(s): {manual_paths - set(execution._MANUAL)}"
    )
    for m in report["manual"]:
        assert m["reason"] == execution._MANUAL[m["path"]]
    # A registered exemption must still be a live citation: either it is reported MANUAL or a
    # caller upgraded it to EXECUTED. A _MANUAL entry matching NO citation is dead vocabulary.
    cited = {r["path"]: r["verdict"] for r in report["citations"]}
    for path in execution._MANUAL:
        assert cited.get(path) in ("MANUAL", "EXECUTED"), (
            f"_MANUAL entry {path} resolves to {cited.get(path)!r} -- exemption without a citation"
        )
