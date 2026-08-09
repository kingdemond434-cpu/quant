from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_permission_matrix_denies_research_write_and_service_control() -> None:
    matrix = json.loads((ROOT / "deploy/privilege_separation/permission_matrix.json").read_text())
    research = [r for r in matrix["rules"] if r["principal"] == "quant"]
    assert {r["access"] for r in research} <= {"read-only", "none"}
    assert any("systemd" in r["path"] and r["access"] == "none" for r in research)


def test_service_executes_root_owned_copy_under_nonlogin_account() -> None:
    unit = (ROOT / "deploy/privilege_separation/quant-risk-kernel.service").read_text()
    installer = (ROOT / "deploy/privilege_separation/install.sh").read_text()
    assert "User=quant-risk" in unit
    assert "ExecStart=/opt/quant-risk-kernel/" in unit
    assert "/home/quant/quant-platform/scripts/run_deadman_switch.py" not in unit
    assert "cp -a" in installer and "chown -R root:quant-risk" in installer
    assert "systemctl start" not in installer  # host starts only after explicit reconciliation
