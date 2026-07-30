"""The Holm cohort is the desk's only multiplicity control on the only path to capital.

These tests pin the FAIL-SAFE DIRECTION, not just the arithmetic: understating m loosens every
Stage-B bar, which is the phantom-edge direction, so every degenerate case must push m UP (or
flag itself), never down.
"""
from __future__ import annotations

import json

import pytest

from libs.research import slot_registry as sr
from libs.validation.forward_stats import holm_bar


@pytest.fixture
def fake_root(tmp_path, monkeypatch):
    """A throwaway repo root so tests never read (or write) the live clock artifacts."""
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(sr, "_ROOT", tmp_path)
    return tmp_path


def _write(root, rel, payload):
    (root / rel).write_text(json.dumps(payload), "utf-8")


def test_counts_axis_standing_and_derivative_clocks(fake_root):
    _write(fake_root, "data/axis_shadow_state.json",
           {"axes": [{"axis": "kimchi", "verdict": "ACCRUING"},
                     {"axis": "cny", "verdict": "ACCRUING"}]})
    _write(fake_root, "data/cashcarry_shadow_state.json", {"shadow_start": "2026-06-26"})
    _write(fake_root, "data/shadow_sleeves.json", [])

    snap = sr.derive_slots()
    kinds = {s["kind"] for s in snap["slots"]}
    # 2 axis + 1 standing + 2 built-in derivative sleeves
    assert snap["m_concurrent"] == 5
    assert kinds == {"axis", "standing", "derivative"}


def test_retired_axis_leaves_the_cohort(fake_root):
    _write(fake_root, "data/axis_shadow_state.json",
           {"axes": [{"axis": "live", "verdict": "ACCRUING"},
                     {"axis": "dead", "verdict": "RETIRED"}]})
    _write(fake_root, "data/shadow_sleeves.json", [])

    names = {s["name"] for s in sr.derive_slots()["slots"]}
    assert "live" in names
    assert "dead" not in names


def test_unreadable_source_flags_incomplete_rather_than_counting_zero(fake_root):
    """A vanished clock file must never silently shrink m -- that would loosen every bar."""
    _write(fake_root, "data/axis_shadow_state.json",
           {"axes": [{"axis": "a", "verdict": "ACCRUING"}]})
    (fake_root / "data" / "cashcarry_shadow_state.json").write_text("{not json", "utf-8")

    snap = sr.derive_slots()
    assert snap["complete"] is False
    assert "data/cashcarry_shadow_state.json" in snap["unknown_sources"]


def test_registry_extras_are_added_to_the_builtin_sleeves(fake_root):
    _write(fake_root, "data/axis_shadow_state.json", {"axes": []})
    _write(fake_root, "data/shadow_sleeves.json", ["challenger_x"])

    deriv = {s["name"] for s in sr.derive_slots()["slots"] if s["kind"] == "derivative"}
    assert deriv == {"oi_divergence", "ls_contrarian", "challenger_x"}


def test_concurrent_m_never_returns_zero(fake_root):
    """m=0 would make holm_bar divide multiplicity away entirely -- an unbounded bar collapse."""
    _write(fake_root, "data/axis_shadow_state.json", {"axes": []})
    _write(fake_root, "data/shadow_sleeves.json", [])
    for rel in sr._STANDING_STATES.values():
        _write(fake_root, rel, {})
    # only the two built-in derivative sleeves survive; even at zero it must floor at 1
    assert sr.concurrent_m() >= 1


def test_bar_tightens_as_the_cohort_grows(fake_root):
    """The regression this module exists to stop: m=4 gave 2.24 while 12 clocks accrued (2.64)."""
    assert holm_bar(4, rank=1) == pytest.approx(2.24)
    assert holm_bar(12, rank=1) == pytest.approx(2.64)
    assert holm_bar(12, rank=1) > holm_bar(4, rank=1)


def test_over_cap_and_idle_are_both_reported(fake_root):
    _write(fake_root, "data/axis_shadow_state.json",
           {"axes": [{"axis": f"a{i}", "verdict": "ACCRUING"} for i in range(20)]})
    _write(fake_root, "data/shadow_sleeves.json", [])
    over = sr.derive_slots()
    assert over["over_cap"] is True
    assert over["idle_slots"] == 0

    _write(fake_root, "data/axis_shadow_state.json", {"axes": []})
    idle = sr.derive_slots()
    assert idle["over_cap"] is False
    assert idle["idle_slots"] == sr.MAX_FORWARD_SLOTS - idle["m_concurrent"]
