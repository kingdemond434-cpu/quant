"""Alpha cards and the metric models used by health/decay/ranking."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from libs.alpha.state import AlphaState


class NewAlpha(BaseModel):
    """Input to register a new alpha (becomes a CANDIDATE card)."""

    model_config = ConfigDict(frozen=True)

    name: str
    market: str
    category: str
    thesis: str
    entry_logic: str
    exit_logic: str
    expected_cagr: float | None = None
    expected_sharpe: float | None = None
    expected_drawdown: float | None = None
    dsr: float | None = None
    pbo: float | None = None
    cpcv: dict[str, Any] | None = None
    walk_forward: dict[str, Any] | None = None
    holdout: dict[str, Any] | None = None
    predecessor_id: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class AlphaCard(BaseModel):
    """The full alpha card — an immutable read snapshot of one alpha's record."""

    model_config = ConfigDict(frozen=True)

    id: str
    created_at: str
    updated_at: str
    name: str
    market: str
    category: str
    thesis: str
    entry_logic: str
    exit_logic: str
    expected_cagr: float | None
    expected_sharpe: float | None
    expected_drawdown: float | None
    dsr: float | None
    pbo: float | None
    cpcv: dict[str, Any] | None
    walk_forward: dict[str, Any] | None
    holdout: dict[str, Any] | None
    deployment_date: str | None
    retirement_date: str | None
    live_cagr: float | None
    live_sharpe: float | None
    live_drawdown: float | None
    decay_score: float
    status: AlphaState
    successor_id: str | None
    predecessor_id: str | None
    extra: dict[str, Any]


class ExpectedMetrics(BaseModel):
    """Backtest expectations a live alpha is measured against."""

    model_config = ConfigDict(frozen=True)

    sharpe: float | None = None
    cagr: float | None = None
    max_drawdown: float | None = None  # positive magnitude
    win_rate: float | None = None
    profit_factor: float | None = None
    expectancy: float | None = None
    trade_mean: float | None = None
    trade_std: float | None = None

    @classmethod
    def from_card(cls, card: AlphaCard) -> ExpectedMetrics:
        extra = card.extra or {}
        return cls(
            sharpe=card.expected_sharpe,
            cagr=card.expected_cagr,
            max_drawdown=card.expected_drawdown,
            win_rate=extra.get("expected_win_rate"),
            profit_factor=extra.get("expected_profit_factor"),
            expectancy=extra.get("expected_expectancy"),
            trade_mean=extra.get("expected_trade_mean"),
            trade_std=extra.get("expected_trade_std"),
        )


class LiveMetrics(BaseModel):
    """Measured live performance for an alpha."""

    model_config = ConfigDict(frozen=True)

    sharpe: float
    cagr: float
    max_drawdown: float  # positive magnitude
    win_rate: float | None = None
    profit_factor: float | None = None
    expectancy: float | None = None
    regime_stability: float = 1.0  # 1 = stable, 0 = fully regime-mismatched
    trade_mean: float | None = None
    trade_std: float | None = None
    sample: int = 0


class AlphaEvent(BaseModel):
    """One immutable lifecycle audit record."""

    model_config = ConfigDict(frozen=True)

    seq: int
    id: str
    alpha_id: str
    created_at: str
    event_type: str
    from_status: str | None
    to_status: str | None
    detail: dict[str, Any] | None
    actor: str


class AlphaPerformance(BaseModel):
    """One live-performance snapshot."""

    model_config = ConfigDict(frozen=True)

    id: str
    alpha_id: str
    created_at: str
    sharpe: float | None
    cagr: float | None
    max_drawdown: float | None
    win_rate: float | None
    profit_factor: float | None
    expectancy: float | None
    sample: int | None
