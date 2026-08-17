"""The desk has ONE risk budget, and every consumer must read the same one.

`allocation.py` optimised and reported the book at Q_TOTAL = 0.055 for as long as it took anyone
to notice, while the gateway had moved to 0.0075 -- a seven-fold disagreement about how much of
the account is at risk per trade, sitting in two files that never compare notes. The number is
now sourced rather than copied; this fences it so a copy cannot reappear.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk.gateway_config_fallback import (  # noqa: E402
    BOOK_WORST_DD_R, MAX_DRAWDOWN_TOLERANCE, Q_OPT, risk_per_trade)

_GW = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")


def test_the_gateway_imports_the_budget_rather_than_restating_it():
    """THE COPY IS GONE, not merely synchronised. This test used to assert that gateway.py's
    literal EQUALLED the fallback's -- and it earned its keep, catching the drift the first time
    the gateway's value changed. But a test is a poor substitute for an invariant: two constants
    that must agree stay agreed only while someone remembers to check. The gateway now imports."""
    assert not re.search(r"^Q_OPT\s*=\s*[0-9]", _GW, re.M), (
        "gateway.py defines its own Q_OPT literal again -- the second copy is back")
    assert "from mt5desk.gateway_config_fallback import" in _GW
    assert "Q_OPT," in _GW or "Q_OPT " in _GW


def test_risk_per_trade_spends_exactly_the_stated_tolerance():
    """The derivation, checked against its own definition: losing q of equity on each of dd_r
    consecutive R must land on the tolerance, not near it."""
    realised = 1.0 - (1.0 - Q_OPT) ** BOOK_WORST_DD_R
    assert realised == pytest.approx(MAX_DRAWDOWN_TOLERANCE, abs=1e-9)


def test_a_worse_drawdown_estimate_produces_a_smaller_q():
    """Monotonicity, so a future revision to the book's worst drawdown moves size the right way."""
    assert risk_per_trade(dd_r=50.0) < Q_OPT < risk_per_trade(dd_r=20.0)
    assert risk_per_trade(tolerance=0.20) < Q_OPT < risk_per_trade(tolerance=0.50)


def test_the_book_cannot_absorb_a_meaningful_drawdown_haircut():
    """WHY THERE IS NO SAFETY FACTOR ON THE IN-SAMPLE -33.7R, stated as a test so the next person
    to reach for one finds the arithmetic instead of re-deriving it. At EUR 1,684 the 0.01 lot
    floor forces 1.04% per trade and the armed book runs three legs = 3.12%. A haircut past ~1.22x
    puts the base budget under that and amputates a validated leg."""
    floor_q, legs = 0.0104, 3
    assert risk_per_trade(dd_r=BOOK_WORST_DD_R * 1.22) * legs >= floor_q * legs
    assert risk_per_trade(dd_r=BOOK_WORST_DD_R * 1.5) * legs < floor_q * legs, (
        "a 1.5x haircut now fits -- the account grew, so a safety factor is affordable; "
        "revisit BOOK_WORST_DD_R")


def test_no_consumer_hardcodes_its_own_risk_budget():
    """A literal 0.055 anywhere outside the gateway's own explanatory comment is the exact defect
    this fences: a superseded number that still reads like a decision."""
    # ONE designated holder now. gateway_config_fallback.py defines the budget; gateway.py used to
    # be exempt as its co-owner and no longer needs to be, because it imports like everyone else.
    HOLDERS = {"gateway_config_fallback.py"}
    offenders = []
    for py in _DESK.rglob("*.py"):
        if "__pycache__" in py.parts or py.name in HOLDERS:
            continue
        if py.name.startswith("test_"):
            continue
        for i, line in enumerate(py.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            code = line.split("#")[0]
            if re.search(r"\b(Q_TOTAL|Q_OPT|q_total|q_opt)\s*=\s*0\.0\d+", code):
                offenders.append(f"{py.relative_to(_DESK)}:{i}: {line.strip()}")
    assert not offenders, (
        "risk budget hardcoded instead of imported:\n  " + "\n  ".join(offenders))


def test_the_budget_is_far_below_measured_full_kelly():
    """Measured full Kelly on the 3-leg gold book is 6.00%. Kelly is computed FROM an in-sample
    edge and is the point of maximum sensitivity to that edge being overstated, so the budget
    must sit well under it. Half Kelly (3%) is still a -68% historical drawdown."""
    assert 0 < Q_OPT <= 0.015, (
        f"Q_OPT={Q_OPT} is at or above half of measured full Kelly (6.00%). At 3% the historical "
        "path draws down 68%, at 5.5% it draws down 91%. Raising this is a claim about forward "
        "evidence and needs live trades behind it, not a backtest.")
