"""Tests for the cash-carry executor's open-sizing (the 2026-07-13 NOMUSDT incident class).

The concentration cap in ``_alloc`` must be HARD: with 1-2 candidates it used to "relax" and
pile the whole book's capital into one name -- $4,297 of a $4,500 book went into a single
micro-cap and fired the dead-man rail. These tests pin the fixed semantics: per-name notional
never exceeds cap_frac * capital, whatever the candidate count; the un-deployable remainder
stays in cash.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "run_cashcarry_executor.py"
_SPEC = importlib.util.spec_from_file_location("run_cashcarry_executor", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)

_alloc = _MOD._alloc


def test_single_candidate_never_gets_more_than_cap() -> None:
    # the exact 2026-07-13 shape: one fresh open, everything else held
    out = _alloc([("NOMUSDT", 0.000146)], 4500.0)
    assert out["NOMUSDT"] <= 0.35 * 4500.0 + 1e-6


def test_two_candidates_each_capped() -> None:
    out = _alloc([("GTCUSDT", 0.0008), ("NOMUSDT", 0.0001)], 4500.0)
    assert all(v <= 0.35 * 4500.0 + 1e-6 for v in out.values())


def test_zero_funding_equal_weight_branch_is_capped_too() -> None:
    out = _alloc([("AUSDT", 0.0)], 4500.0)
    assert out["AUSDT"] <= 0.35 * 4500.0 + 1e-6


def test_feasible_book_still_deploys_full_capital() -> None:
    cands = [(f"S{i}USDT", 0.0001 * (i + 1)) for i in range(10)]
    out = _alloc(cands, 4500.0)
    assert abs(sum(out.values()) - 4500.0) < 1e-6          # water-fill conserves when feasible
    assert max(out.values()) <= 0.35 * 4500.0 + 1e-6


def test_extreme_funding_skew_holds_the_cap() -> None:
    cands = [("HOTUSDT", 0.01)] + [(f"S{i}USDT", 1e-6) for i in range(9)]
    out = _alloc(cands, 4500.0)
    assert out["HOTUSDT"] <= 0.35 * 4500.0 + 1e-6
    assert abs(sum(out.values()) - 4500.0) < 1e-6
