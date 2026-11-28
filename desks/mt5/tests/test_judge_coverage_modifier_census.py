"""The trial-charge jump a new modifier definition causes is recorded as a named census."""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for p in (str(DESK), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import cell_modifiers as cm  # noqa: E402
from research import judge_coverage as jc  # noqa: E402


def _rows() -> list[dict]:
    return [{"family": "a", "regime": "risk_on"},
            {"family": "a", "params": {"regime": "RISK_OFF"}},
            {"family": "b", "params": {"regime": "risk_off"}},
            {"family": "b", "regime": "high_vol"},
            {"family": "c"}]


def test_the_census_counts_cells_whose_regime_just_gained_a_definition() -> None:
    md = jc.modifier_definitions(_rows(), {})
    assert md["status"] == "MEASURED"
    assert md["version"] == cm.DEFINITIONS_VERSION
    assert md["newly_judgeable_by_regime"] == {"risk_off": 2, "risk_on": 1}
    assert md["newly_judgeable"] == 3
    assert md["changed"] is True and md["prior_version"] is None


def test_a_pass_on_the_same_version_is_not_a_change() -> None:
    md = jc.modifier_definitions(_rows(), {"modifier_definitions_version": cm.DEFINITIONS_VERSION})
    assert md["changed"] is False


def test_a_changed_version_emits_one_event(monkeypatch) -> None:
    import libs.ops.events as ev

    got: list[tuple] = []
    monkeypatch.setattr(ev, "emit", lambda kind, path=None, **f: got.append((kind, f)))
    jc._emit_modifier_defined(jc.modifier_definitions(_rows(), {}))
    assert got and got[0][0] == "MODIFIER_DEFINED"
    assert got[0][1]["newly_judgeable"] == 3
    assert "MODIFIER_DEFINED" in ev.KINDS
