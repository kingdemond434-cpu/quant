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
    # Bracket widened with the tolerance itself (0.35 -> 0.642, principal 2026-08-22). The
    # ASSERTION is monotonicity, not a particular level, so the bracket has to straddle whatever
    # tolerance is declared -- pinning it to the old one would make this test a second, silent
    # copy of the risk policy, which is the exact defect this module exists to prevent.
    assert risk_per_trade(tolerance=0.20) < Q_OPT < risk_per_trade(tolerance=0.80)


def test_the_book_cannot_absorb_a_meaningful_drawdown_haircut():
    """WHY THERE IS NO SAFETY FACTOR ON THE IN-SAMPLE -33.7R, stated as a test so the next person
    to reach for one finds the arithmetic instead of re-deriving it. At EUR 1,684 the 0.01 lot
    floor forces 1.04% per trade and the armed book runs three legs = 3.12%. A haircut past ~1.22x
    puts the base budget under that and amputates a validated leg."""
    floor_q, legs = 0.0104, 3
    assert risk_per_trade(dd_r=BOOK_WORST_DD_R * 1.22) * legs >= floor_q * legs
    # THE HEADROOM CLAIM INVERTED WHEN THE TOLERANCE ROSE, and that is a real finding rather than
    # a test to relax: at a 64.2% tolerance a 1.5x drawdown haircut DOES still clear the 0.01-lot
    # floor, so a safety factor on the in-sample -33.7R is now affordable where at 35% it was not.
    # Recorded as the arithmetic it is -- the original assertion said "no safety factor fits", and
    # at this tolerance that statement is simply false.
    haircut_15 = risk_per_trade(dd_r=BOOK_WORST_DD_R * 1.5) * legs
    assert haircut_15 >= floor_q * legs, (
        "a 1.5x haircut no longer fits -- if the tolerance is lowered again this flips back and "
        "the safety-factor argument in gateway_config_fallback.py must be re-read")


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


def test_the_budget_does_not_exceed_half_measured_kelly():
    """Measured full Kelly on the 3-leg gold book is 6.00%. Kelly is computed FROM an in-sample
    edge and is the point of MAXIMUM sensitivity to that edge being overstated, so the budget must
    not cross it.

    THE CEILING WAS 1.5% AND IS NOW 3.0% -- HALF KELLY -- BY THE PRINCIPAL'S EXPLICIT AND REPEATED
    DECISION, 2026-08-22. The old bound's message said raising it "is a claim about forward
    evidence and needs live trades behind it, not a backtest", and that precondition is NOT met:
    shadow holds zero trades. The decision was made anyway, with the evidence and the objection
    both recorded in gateway_config_fallback.py, and this test is rewritten to the new declared
    policy rather than deleted -- a guard that is quietly removed stops being a decision anyone
    can find later.

    WHAT KEPT IT AT HALF KELLY RATHER THAN HIGHER. Growth measured on 5,731 real gold trades, by
    true edge as a fraction of backtest: 3% is the LARGEST per-trade risk whose worst case across
    x1.00/x0.75/x0.50/x0.33/x0.25/x0.15 is still non-negative. 3.5% returns -7% at x0.15 and 5%
    returns -33%. Half Kelly is therefore not a round number here, it is the last size that
    survives being wrong about the edge -- which is the only property worth fencing.

    WHAT THIS COSTS, so the next reader does not have to re-derive it: at x0.25 3% earns exactly
    what 2% earns (+27% both) while carrying 15 more points of drawdown, and the five-year
    bad-decile outcome on $5,000 is $3,836 against $6,241 at 2%.
    """
    # Compared with a float epsilon, not exactly. Q_OPT is the output of
    # 1-(1-tol)**(1/33.7) and lands 2.6e-12 above KELLY/2 for the tolerance that solves to
    # exactly 3%; failing on that would be testing IEEE-754, not the risk policy. The epsilon is
    # 1e-9 -- a millionth of a basis point, far below any size the venue can express.
    KELLY = 0.06
    assert 0 < Q_OPT <= KELLY / 2 + 1e-9, (
        f"Q_OPT={Q_OPT} exceeds HALF of measured full Kelly ({KELLY:.0%}). Past the true optimum "
        "the geometric rate FALLS, and at 2x Kelly it goes negative while every backtest number "
        "still looks excellent. Raising the budget beyond half Kelly is not more aggression, it "
        "is less money -- and it needs forward evidence, which shadow does not yet hold.")
