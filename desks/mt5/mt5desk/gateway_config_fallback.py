"""Risk-budget constants readable WITHOUT importing the gateway.

`gateway.py` imports MetaTrader5, which only exists on the Windows execution box. Research code
on Linux still has to know the desk's risk budget, and the failure mode when it cannot is silent
and expensive: the importer falls back to a literal it defines itself, and that literal is
whatever was true when the file was written. `allocation.py` was optimising at 0.055 for exactly
that reason, long after the gateway moved to 0.0075.

This module holds the number with NO heavy imports, and `gateway.py` is the one that must agree
with it -- asserted by tests/test_risk_budget_single_source.py.
"""

from __future__ import annotations

#: Risk fraction of equity per trade. See gateway.Q_OPT for the full derivation (measured full
#: Kelly on the 3-leg gold book is 6.00%; this sits far below it because Kelly is computed from
#: an in-sample edge and is maximally sensitive to that edge being overstated).
Q_OPT = 0.0075
