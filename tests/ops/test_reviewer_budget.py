"""The independent reviewer's time budget frees its runner (Autonomy, 2026-11-11).

Running out of budget only ever ends UNAVAILABLE (exit 75): it can never turn into a PASS.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _ir():
    path = ROOT / "ops/release/independent_review.py"
    spec = importlib.util.spec_from_file_location("independent_review", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_budget_is_an_hour_at_most_and_still_fits_one_call() -> None:
    ir = _ir()
    assert ir.BUDGET_S <= 60 * 60
    assert ir.BUDGET_S >= ir.CALL_TIMEOUT_S


def test_out_of_budget_is_unavailable_never_a_pass() -> None:
    ir = _ir()
    assert ir.UNAVAILABLE == 75
    t = iter([0.0] + [10.0 * ir.BUDGET_S] * 1000)
    asked: list[str] = []

    def never(*a, **k):
        asked.append("x")
        raise AssertionError("no model may be asked once the budget is spent")

    verdict, _log = ir.vote(
        "diff --git a/x b/x\n+1\n", ["x"], [("m", "fam", never)], ir.BUDGET_S,
        lambda s: None, lambda: next(t),
    )
    assert not asked
    assert verdict == "UNAVAILABLE"
