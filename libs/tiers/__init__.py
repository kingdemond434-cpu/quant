"""TIER S: the autonomous quant research institution's kernel.

Every module here is a pure library (no clocks, no file layout assumptions beyond what a caller
passes in). `desks/mt5/research/tier_s.py` is the organ that runs them hourly against the desk's
own artifacts, and `docs/research/tier_s_program.json` is the machine-checked ledger that says,
per layer, which file implements it, which clock runs it, which artifact it writes and which
measurable gain it is admitted for (`libs/tiers/contracts.py`). A layer with no measurable gain
does not ship: that is the principal's closing rule of 2026-09-29.
"""
