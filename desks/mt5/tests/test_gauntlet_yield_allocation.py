"""The build budget must follow survivors, not cell counts.

Measured on the live desk 2026-09-14, survivors per 1,000 RULED cells:
`session_range_breakout` 105.6, `overnight_gap_decay` 60.9, `discovered` 2.0 -- and `discovered`
was taking 84% of every sweep because it simply had the most cells. Nothing chose that: the sweep
builds in symbol-rotation order, so the docket's SHAPE was the allocation policy.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "_gaunt", ROOT / "desks" / "mt5" / "scripts" / "external_gauntlet.py")
assert _spec and _spec.loader
sys.path.insert(0, str(ROOT / "desks" / "mt5"))


def _specs(counts: dict[str, int]) -> list[dict]:
    return [{"sym": f"S{i}", "family": fam, "params": {}}
            for fam, n in counts.items() for i in range(n)]


def test_a_productive_family_gets_more_of_the_sweep_than_its_cell_count_implies(
        monkeypatch) -> None:
    g = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(g)
    # One family with 100x the cells and a fiftieth of the yield -- the live shape, scaled down.
    monkeypatch.setattr(g, "_family_yield", lambda root=None: {
        "session_range_breakout": 0.1056, "discovered": 0.0020})
    specs = _specs({"discovered": 1000, "session_range_breakout": 10})
    kept, report = g.allocate_by_yield(specs)

    d, s = report["discovered"], report["session_range_breakout"]
    # The productive family keeps ALL of its cells -- its share exceeds its docket -- while the
    # unproductive one is trimmed. That is the whole point: the hour stops being spent on volume.
    assert s["built_this_sweep"] == 10, "a high-yield family must never be the one trimmed"
    assert d["built_this_sweep"] < 1000, "the 84% family must give budget back"
    assert d["share_of_budget"] < s["share_of_budget"] + 1.0  # sanity: shares are comparable
    assert len(kept) < len(specs)


def test_a_family_with_no_survivors_is_throttled_but_never_starved(monkeypatch) -> None:
    """Exploration is not charity: a family cannot update a yield it is never allowed to earn.

    Starve one completely and its record can never change, so a single bad epoch would condemn it
    permanently. The floor is the fence against that feedback loop.
    """
    g = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(g)
    monkeypatch.setattr(g, "_family_yield", lambda root=None: {
        "session_range_breakout": 0.1056, "pca_residual": 0.0})
    specs = _specs({"pca_residual": 400, "session_range_breakout": 100})
    _, report = g.allocate_by_yield(specs)

    zero = report["pca_residual"]
    assert zero["built_this_sweep"] >= int(g.YIELD_MIN_SHARE * 400), "floor must hold"
    assert zero["built_this_sweep"] < 400, "and it must still be throttled"


def test_an_unmeasured_family_is_credited_with_the_house_average(monkeypatch) -> None:
    """Neither condemned nor privileged before it has evidence."""
    g = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(g)
    monkeypatch.setattr(g, "_family_yield", lambda root=None: {})
    specs = _specs({"brand_new": 50, "also_new": 50})
    _, report = g.allocate_by_yield(specs)
    a, b = report["brand_new"], report["also_new"]
    assert a["share_of_budget"] == b["share_of_budget"], (
        "with no evidence, two families must be treated identically")
