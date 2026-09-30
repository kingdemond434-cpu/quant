"""ALLOCATOR SOVEREIGNTY -- principal, 2026-09-29, superseding the 2026-09-07 gold floor and the
2026-09-12 "every sleeve trades at least the venue minimum" order.

    python -m pytest desks/mt5/tests/test_allocator_sovereignty.py -q

The optimiser is the final capital authority:
  1. a target of zero sends no order (gold included)
  2. a positive target below the symbol's own venue minimum sends no order -- never rounded up
  3. a positive target at or above the minimum is sent at exactly the allocator's fraction
  4. data/ALLOCATOR_SOVEREIGN.json {"enabled": false} restores the legacy floors without a push
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import decision_core as core  # noqa: E402
from mt5desk import sizing  # noqa: E402


@pytest.fixture(autouse=True)
def _sovereign(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    f = tmp_path / "ALLOCATOR_SOVEREIGN.json"
    monkeypatch.setattr(core, "ALLOCATOR_SOVEREIGN", True)
    monkeypatch.setattr(core, "ALLOCATOR_SOVEREIGN_FILE", f)
    return f


# ------------------------------------------------------------------ 1. zero is zero

def test_a_zeroed_book_sleeve_sends_nothing() -> None:
    assert core.promoted_lot(607.68, 100, dist_usd=0.005, symbol="EURUSD",
                             risk_frac=0.0, from_book=True) == 0.0


def test_a_zeroed_gold_window_sends_nothing() -> None:
    lot, why = core.gold_book_lot(8000.0, 20.0, None, 0.0)
    assert lot == 0.0 and "no heat" in why


# ------------------------------------------------------------------ 2. below minimum is skip

def test_a_positive_target_below_the_minimum_is_skipped_not_lifted() -> None:
    lot = core.promoted_lot(300.0, 500, dist_usd=0.02, symbol="EURUSD",
                            risk_frac=0.001, from_book=True)
    assert lot == 0.0, "rounding UP to the venue minimum makes the minimum a prior on every sleeve"


def test_gold_below_its_minimum_is_skipped() -> None:
    lot, why = core.gold_book_lot(300.0, 50.0, None, 0.001)
    assert lot == 0.0 and "below the venue minimum" in why
    assert core.gold_lot(50.0, 50.0) == 0.0


def test_risk_lot_refuses_rather_than_lifts() -> None:
    assert sizing.risk_lot(100.0, 0.05, 1.0, 1e-5, 0.01, 0.01, 50.0) == 0.0


def test_implementable_lot_snaps_down_and_never_up() -> None:
    assert core.implementable_lot(0.0099, "EURUSD") == 0.0
    assert core.implementable_lot(0.0199, "EURUSD") == 0.01
    assert core.implementable_lot(-1.0, "EURUSD") == 0.0
    assert core.implementable_lot(99.0, "EURUSD") == 5.0


# ------------------------------------------------------------------ 3. the fraction is the size

def test_gold_is_sized_at_the_allocators_fraction_alone() -> None:
    eq, dist, h = 50_000.0, 20.0, 0.004
    lot, why = core.gold_book_lot(eq, dist, None, h)
    raw = h * eq / (dist * core._eur_per_price_unit(core.GOLD_SYMBOL, None))
    assert lot == pytest.approx(core._lot_steps(raw))
    assert why.startswith("sovereign: allocator_book")


def test_a_funded_book_sleeve_is_sent_at_its_fraction() -> None:
    eq, dist, h = 100_000.0, 0.005, 0.01
    lot = core.promoted_lot(eq, 500, dist_usd=dist, symbol="EURUSD", risk_frac=h,
                            from_book=True)
    raw = h * eq / (dist * core._eur_per_price_unit("EURUSD", None))
    assert lot == pytest.approx(min(core._lot_steps(raw), 5.0))
    assert lot > 0.0


# ------------------------------------------------------------------ 4. the revert path

def test_the_file_switch_restores_the_legacy_floors(_sovereign: Path) -> None:
    _sovereign.write_text(json.dumps({"enabled": False}), encoding="utf-8")
    assert core.allocator_sovereign() is False
    assert core.promoted_lot(607.68, 100, dist_usd=0.005, symbol="EURUSD",
                             risk_frac=0.0, from_book=True) == core.venue_min_lot("EURUSD")


def test_an_unreadable_switch_stays_sovereign(_sovereign: Path) -> None:
    _sovereign.write_text("{ nope", encoding="utf-8")
    assert core.allocator_sovereign() is True
