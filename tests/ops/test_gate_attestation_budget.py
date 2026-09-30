"""The gate verdict recorder must outlive its own bounded Git observations."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_attestation_record_budget_covers_three_bounded_git_reads() -> None:
    path = ROOT / "scripts" / "run_gate_attestation.py"
    spec = importlib.util.spec_from_file_location("run_gate_attestation", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.ATTEST_RECORD_TIMEOUT_S >= 3 * 60
