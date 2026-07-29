"""Hypothesis-max machinery (HYPOTHESIS_MAX_SPEC.md).

DELIBERATELY EMPTY, and deliberately NOT in libs/alpha_factory. Importing that package pulls
duckdb, pandas and scipy transitively -- measured, not assumed. A pre-filter whose entire purpose
is to reject candidates BEFORE heavy compute must not cost a multi-second import to ask a
question answerable with arithmetic. Same reasoning that put libs/metrics outside libs/backtest.
"""
