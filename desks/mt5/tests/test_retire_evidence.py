"""Retiring is as consequential as promoting and must not fire on a broken series.

Measured 2026-09-01: gold_asia was auto-retired on n=30 with exp EXACTLY -1.000R and max_dd
-29.0 -- thirty consecutive losses of precisely one R -- on the same day the account those
sleeves trade went 500.00 -> 603.84. A constant series is the signature of a broken r_multiple
computation; stopping a live book on it looks identical to a verdict afterwards.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parent.parent
for p in (str(DESK), str(DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import promoter as P  # noqa: E402


def _rows(name: str, values: list[float]) -> list[dict]:
    return [{"sleeve": name, "r_multiple": v} for v in values]


def test_the_exact_series_that_retired_gold_asia_is_refused() -> None:
    rows = _rows("gold_asia", [-1.0] * 30)
    stats = P.sleeve_forward_stats(rows, "gold_asia")
    # the incident, reproduced from its own recorded numbers
    assert stats == {"n": 30, "exp": -1.0, "max_dd": -29.0, "roll20_exp": -1.0}
    assert stats["n"] >= P.RETIRE_MIN_N and stats["roll20_exp"] <= 0.0, (
        "guard would be pointless if the rule did not otherwise fire on this")
    assert P.degenerate_evidence(rows, "gold_asia"), "a constant series must refuse retirement"


def test_a_genuinely_losing_sleeve_is_still_retired() -> None:
    """The guard must cost nothing: no threshold is softened, only defect-shaped input refused."""
    rng = random.Random(3)
    vals = [round(rng.uniform(-2.0, 0.6), 3) for _ in range(30)]
    rows = _rows("gold_asia", vals)
    assert not P.degenerate_evidence(rows, "gold_asia")
    fs = P.sleeve_forward_stats(rows, "gold_asia")
    assert fs["n"] >= P.RETIRE_MIN_N and fs["roll20_exp"] <= 0.0, "this fixture must be a loser"


def test_all_zero_r_multiples_are_refused() -> None:
    """r = 0.0 is what record_trades writes when risk_per_lot is unmeasurable, not a flat book."""
    assert P.degenerate_evidence(_rows("g", [0.0] * 12), "g")


def test_an_empty_or_single_row_ledger_expresses_no_opinion() -> None:
    assert P.degenerate_evidence([], "g") == ""
    assert P.degenerate_evidence(_rows("g", [-1.0]), "g") == ""


def test_one_differing_value_is_enough_dispersion() -> None:
    assert not P.degenerate_evidence(_rows("g", [-1.0] * 29 + [-0.5]), "g")
