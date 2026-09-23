"""TURKEY -- the desk's only fully liquid high-carry currency, and its most expensive one.

USDTRY IS EXECUTABLE AND IT IS NOT CHEAP. Measured on this box 2026-09-17: 37,394 H1 bars to
2026-09-16, a median H1 spread over the last sixty days of 405 points (about 8bp on a rate of
48.66), and ZERO frozen bars -- a working market, unlike the Russian tape next door. The cost is
not in the spread, it is in the CARRY: the broker's swap table charges -10,921 points per lot per
night to hold long USDTRY and pays +1,481 to hold it short, an asymmetry of roughly 7.4 to one.
Every Turkish cell is therefore direction-dependent by construction, and a symmetric cost
assumption flatters the depreciation trade enormously. `TR-E` exists to keep that honest.

Four mechanics belong to this economy and to no other in the desk's book:

  * A CONTINGENT FISCAL LIABILITY THAT GROWS WITH DEPRECIATION. FX-protected deposits (kur
    korumalı mevduat) pay the depositor the difference when the lira falls by more than the
    deposit rate. The stock is published weekly, so the state's exposure to its own currency is
    a dated public number -- and it is a feedback loop, because the payout is financed in lira.
  * A DISPUTED INFLATION PRINT. TÜİK publishes the official CPI and ENAG, an academic group,
    publishes a far higher alternative. The desk keeps BOTH: the official series is what policy
    reacts to, and the gap between them is a measurable, dated expectations variable. ENAG is
    registered CONTRADICTED and kept at low weight rather than dropped.
  * A PHYSICAL GOLD MARKET WITH A FREE-MARKET PREMIUM. Turkey is among the largest bullion
    importers; the Grand Bazaar (Kapalıçarşı) quotes a free-market price whose premium over the
    London-implied gram price is a direct read on household stress that no FX quote provides.
  * A CLOCK THAT NEVER MOVES AND A CALENDAR THAT MOVES ELEVEN DAYS A YEAR. Istanbul has been a
    fixed UTC+3 since 2016, so every Turkish event minute in UTC is stable -- while the two
    Bayram closures drift earlier each year and carry HALF-DAY arifes that a holiday table
    without them will misread as full sessions.
"""
from __future__ import annotations

# ruff: noqa: RUF002
# Turkish dotless i in the docstring; the module has no non-ASCII identifier.

__all__ = ["pack"]
