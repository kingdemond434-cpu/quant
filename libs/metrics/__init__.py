"""``libs.metrics`` -- dependency-free, cross-verified performance metrics.

DELIBERATELY EMPTY. Every other libs package re-exports its modules here, and that is exactly
what made the W3.2 cross-check unusable: `libs.validation.__init__` transitively imports
self_improvement -> discovery -> backtest -> libs.data -> duckdb, and `libs.backtest.__init__`
pulls the same chain plus pydantic-settings. A screen that only wants a Sharpe ratio should not
load a database driver and a settings model, so this package exports nothing eagerly. Import the
module directly:

    from libs.metrics.verified import metrics
"""
