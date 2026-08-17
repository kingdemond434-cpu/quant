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

from mt5desk.gateway_config_fallback import Q_OPT  # noqa: E402


def test_the_fallback_matches_the_gateway():
    """The fallback exists because gateway.py imports MetaTrader5 and cannot load on Linux. That
    makes it a SECOND copy of the number, so it is pinned to the gateway's literal by test rather
    than by hope."""
    src = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
    m = re.search(r"^Q_OPT\s*=\s*([0-9.]+)", src, re.M)
    assert m, "gateway.Q_OPT not found -- did it move or get renamed?"
    assert float(m.group(1)) == pytest.approx(Q_OPT), (
        f"gateway.py says Q_OPT={m.group(1)} but gateway_config_fallback says {Q_OPT}. "
        "Research code reads the fallback; a drift here means the desk optimises one book and "
        "trades another.")


def test_no_consumer_hardcodes_its_own_risk_budget():
    """A literal 0.055 anywhere outside the gateway's own explanatory comment is the exact defect
    this fences: a superseded number that still reads like a decision."""
    # The two DESIGNATED holders are exempt: gateway.py owns the number, and
    # gateway_config_fallback.py restates it for boxes that cannot import MetaTrader5. That
    # restatement is pinned to the gateway by `test_the_fallback_matches_the_gateway`, so it is a
    # checked copy rather than a free-floating one. Everything else must import.
    HOLDERS = {"gateway.py", "gateway_config_fallback.py"}
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
