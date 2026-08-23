from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_zentech_state.py"
SPEC = importlib.util.spec_from_file_location("build_zentech_state", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_missing_values_never_become_fake_zero() -> None:
    assert module._number(None, "missing") is None
    assert module._number(None, 0) == 0.0


def test_dashboard_identity_and_research_fields(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "DESK", tmp_path / "desks" / "mt5")
    payload = module.build()
    assert payload["identity"]["name"] == "ZENTECH"
    assert payload["account"]["equity"] is None
    assert payload["health"]["status"] == "UNMEASURED"
