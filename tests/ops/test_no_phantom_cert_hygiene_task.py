"""box_tasks.manifest must not declare a MT5-CertHygiene task (2026-10-29).

certificate_hygiene.py runs as the first organ of ops/run_frontier_audit.cmd, so it runs inside
MT5-FrontierAudit; no task of its own was ever installed. The manifest carried a placeholder
UNDECLARED row for it that only mirrored the old bare key in ops/organ_contract.py.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "desks" / "mt5" / "ops" / "box_tasks.manifest"


def test_no_phantom_cert_hygiene_task_in_the_manifest() -> None:
    tasks = set(re.findall(r'TASK name="([^"]+)"', MANIFEST.read_text("utf-8")))
    assert "MT5-CertHygiene" not in tasks
    assert "MT5-FrontierAudit" in tasks
