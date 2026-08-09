"""Stable collateral assets -- ONE definition, imported by every venue client.

Both the live and testnet futures clients compute equity as the max of totalMarginBalance and the
face-value sum of per-asset marginBalance across these assets, because under multiAssetsMargin=
False totalMarginBalance is USDT-only and hides the rest (it hid $5,000 of USDC on 2026-07-30,
sizing the book at 1/25th of true wealth and disarming the ruin rail).

This tuple lives here rather than in each client BY DESIGN: two copies of one list drift, and the
copy that drifts is the one nobody is reading. Same lesson as the five copies of the capacity
floor (§42) -- fixing one copy moves the bug, it does not remove it.
"""
from __future__ import annotations

STABLE_COLLATERAL: tuple[str, ...] = ("USDT", "USDC", "FDUSD", "TUSD", "BUSD", "DAI")
