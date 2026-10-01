"""A cell whose chart's history begins after the campaign lockbox cut is carved at its own tail.

Ships WITH patch `unknown_verdict_lockbox_cell_cut.patch` (external_gauntlet.py is sealed).
Measured 2026-09-30 on this tree: the campaign cut landed on 2024-12-19; XAUUSD M15
mean_reversion_rsi fired on 219 trading days, all after it, and was judged on 0 development days.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "scripts"), str(DESK), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import external_gauntlet as eg  # noqa: E402
from research.gate_policy import (  # noqa: E402
    LOCKBOX_MIN_DAYS,
    carve_lockbox,
    lockbox_cut,
)


def _days(start: str, n: int) -> pd.Series:
    return pd.Series(0.01, index=pd.bdate_range(start, periods=n))


def test_the_campaign_cut_leaves_a_late_chart_no_development_window() -> None:
    """The defect, pinned: without the per-cell cut this cell is structurally unjudgeable."""
    long_h1, late_m15 = _days("2018-01-01", 2_200), _days("2025-11-06", 219)
    cut = lockbox_cut([long_h1, late_m15])
    dev, _held = carve_lockbox([long_h1, late_m15], cut)
    assert len(dev[0]) >= 60 and len(dev[1]) == 0


def test_the_cells_own_cut_leaves_sixty_development_days_and_a_full_lockbox() -> None:
    s = _days("2025-11-06", 219)
    own = eg.cell_lockbox_cut(s)
    assert own is not None
    dev, held = s[s.index < own], s[s.index >= own]
    assert len(dev) >= 60 and len(held) >= LOCKBOX_MIN_DAYS
    assert len(dev) + len(held) == len(s), "every day lands on exactly one side"
    assert dev.index.max() < held.index.min(), "the held-out tail is strictly later"


def test_a_history_too_short_for_both_windows_gets_no_own_cut() -> None:
    assert eg.cell_lockbox_cut(_days("2026-06-03", 80)) is None


def test_the_own_cut_is_used_only_where_the_campaign_cut_failed() -> None:
    """`cell_dev_cut` keeps the campaign cut for any cell it leaves judgeable, and for a cell whose
    own cut would not lie later; only a late chart gets its own tail."""
    long_h1, late_m15 = _days("2018-01-01", 2_200), _days("2025-11-06", 219)
    cut = lockbox_cut([long_h1, late_m15])
    assert eg.cell_dev_cut(long_h1, cut) == cut
    own = eg.cell_dev_cut(late_m15, cut)
    assert own == eg.cell_lockbox_cut(late_m15) and own > cut
    assert eg.cell_dev_cut(_days("2026-06-03", 80), cut) == cut, "too short: campaign cut stands"
    assert eg.cell_dev_cut(None, cut) == cut and eg.cell_dev_cut(late_m15, None) is None


def test_the_sweep_and_a_shard_carve_with_the_same_rule() -> None:
    """Source-level pin: `run_gauntlet` and the shard's `rule` phase both carve through
    `cell_dev_cut`, the merge checks a shard's cut against the cell's own, and the stress arm is
    carved at the same per-cell cut as the baseline."""
    src = Path(eg.__file__).read_text("utf-8")
    assert "_cell_cut = [cell_dev_cut(_s, _lock_cut" in src and "for _s in _full_daily]" in src
    assert "x[x.index < _cell_cut[_k]]" in src
    assert '"cut_basis"' in src
    if "def _shard_rule" in src:
        rule = src[src.index("def _shard_rule"):]
        rule = rule[:rule.index("\ndef ", 1)]
        assert "cell_dev_cut(full, cut" in rule and 'c["_local_cut"] = cell_cut' in rule
        assert 'c.get("_local_cut") != _cell_cut[orig_i]' in src
