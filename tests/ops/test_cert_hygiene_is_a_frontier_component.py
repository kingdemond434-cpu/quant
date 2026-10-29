"""certificate_hygiene runs inside MT5-FrontierAudit; its contract must say so (2026-10-29).

ops/organ_contract.py keyed it as a bare task "MT5-CertHygiene" that was never installed, so
process_health raised NOT_SCHEDULED / "never run on this box" every pass against a fresh
artifact, and box_tasks.manifest carried a phantom UNDECLARED row to match.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops"))

from organ_contract import CONTRACTS  # noqa: E402

MANIFEST = ROOT / "desks" / "mt5" / "ops" / "box_tasks.manifest"


def _manifest_tasks() -> set[str]:
    return set(re.findall(r'TASK name="([^"]+)"', MANIFEST.read_text("utf-8")))


def test_cert_hygiene_is_judged_as_a_frontier_component() -> None:
    assert "MT5-CertHygiene" not in CONTRACTS
    artifact, _, _ = CONTRACTS["MT5-FrontierAudit (cert hygiene)"]
    assert artifact == "desks/mt5/reports/CERTIFICATE_HYGIENE.json"
    wrapper = (ROOT / "ops" / "run_frontier_audit.cmd").read_text("utf-8")
    assert re.search(r'^call :run "desks\\mt5\\research\\certificate_hygiene\.py"', wrapper, re.M)


def test_every_component_contract_names_a_manifest_task() -> None:
    """A parenthesised contract is an artifact of its parent task; the parent must exist."""
    tasks = _manifest_tasks()
    orphans = sorted(k for k in CONTRACTS if " (" in k and k.split(" (", 1)[0] not in tasks)
    assert not orphans, orphans
