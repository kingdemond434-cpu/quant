from __future__ import annotations

import importlib.util
import json
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
    assert payload["identity"]["name"] == "QUANT DESK"
    assert payload["account"]["equity"] is None
    assert payload["health"]["status"] == "UNMEASURED"


def test_terminal_shadow_rows_never_display_promotion_authority(
    monkeypatch, tmp_path: Path
) -> None:
    """Retained provenance must not look like a current promotion permission."""
    desk = tmp_path / "desks" / "mt5"
    shadow = desk / "reports" / "shadow"
    shadow.mkdir(parents=True)
    (shadow / "shadow_state.json").write_text(json.dumps({
        "retired": {"status": "RETIRED_ORPHAN", "n": 4, "exp_r": 0.2,
                    "promotion_authority": True},
        "active": {"status": "ACTIVE", "n": 4, "exp_r": 0.2,
                   "promotion_authority": True},
    }), encoding="utf-8")
    (shadow / "qquant_shadow_state.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(module, "DESK", desk)

    rows = {row["name"]: row for row in module._shadow_rows()}
    assert rows["retired"]["source_promotion_authority"] is True
    assert rows["retired"]["promotion_authority"] is False
    assert rows["active"]["promotion_authority"] is True
