"""Per-instrument Fusion cost parameters.

All-in cost is modelled, never the advertised "zero spread": raw spread + commission +
slippage + financing + (optional) gap risk. Defaults are reasoned priors for a Fusion Zero
ECN account and are deliberately conservative; calibrate against realized fills before live.

Round-turn convention: ``spread_price`` is the *full* spread paid over a round turn;
``slippage_price_per_side`` is applied on entry and exit.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from libs.costs.errors import CostError


class CostParams(BaseModel):
    """Cost parameters for one instrument (prices in quote units, money in account ccy)."""

    model_config = ConfigDict(frozen=True)

    instrument: str
    contract_size: float = Field(gt=0)  # units per lot (oz, base ccy, index points)
    commission_per_lot: float = Field(ge=0)  # round-turn commission per lot
    spread_price: float = Field(ge=0)  # full round-turn spread in price units
    slippage_price_per_side: float = Field(ge=0)
    swap_long_per_lot_per_night: float = 0.0  # positive = cost to hold long overnight
    swap_short_per_lot_per_night: float = 0.0
    gap_risk_fraction: float = Field(ge=0, default=0.0)  # expected adverse gap, fraction of price


_DEFAULTS: dict[str, CostParams] = {
    p.instrument: p
    for p in (
        CostParams(
            instrument="EURUSD", contract_size=100_000, commission_per_lot=7.0,
            spread_price=0.00002, slippage_price_per_side=0.00001,
            swap_long_per_lot_per_night=0.7, swap_short_per_lot_per_night=0.3,
            gap_risk_fraction=0.002,
        ),
        CostParams(
            instrument="GBPUSD", contract_size=100_000, commission_per_lot=7.0,
            spread_price=0.00003, slippage_price_per_side=0.000015,
            swap_long_per_lot_per_night=0.8, swap_short_per_lot_per_night=0.4,
            gap_risk_fraction=0.0025,
        ),
        CostParams(
            instrument="USDJPY", contract_size=100_000, commission_per_lot=7.0,
            spread_price=0.003, slippage_price_per_side=0.0015,
            swap_long_per_lot_per_night=0.6, swap_short_per_lot_per_night=0.5,
            gap_risk_fraction=0.002,
        ),
        CostParams(
            instrument="XAUUSD", contract_size=100, commission_per_lot=7.0,
            spread_price=0.12, slippage_price_per_side=0.03,
            swap_long_per_lot_per_night=5.0, swap_short_per_lot_per_night=4.0,
            gap_risk_fraction=0.01,
        ),
        CostParams(
            instrument="XAGUSD", contract_size=5_000, commission_per_lot=7.0,
            spread_price=0.012, slippage_price_per_side=0.004,
            swap_long_per_lot_per_night=4.0, swap_short_per_lot_per_night=3.0,
            gap_risk_fraction=0.015,
        ),
        CostParams(
            instrument="US500", contract_size=1, commission_per_lot=0.0,
            spread_price=0.5, slippage_price_per_side=0.2,
            swap_long_per_lot_per_night=2.0, swap_short_per_lot_per_night=1.5,
            gap_risk_fraction=0.01,
        ),
        CostParams(
            instrument="NAS100", contract_size=1, commission_per_lot=0.0,
            spread_price=1.5, slippage_price_per_side=0.5,
            swap_long_per_lot_per_night=2.5, swap_short_per_lot_per_night=2.0,
            gap_risk_fraction=0.012,
        ),
        CostParams(
            instrument="BTCUSD", contract_size=1, commission_per_lot=0.0,
            spread_price=20.0, slippage_price_per_side=10.0,
            swap_long_per_lot_per_night=15.0, swap_short_per_lot_per_night=12.0,
            gap_risk_fraction=0.03,
        ),
    )
}

DEFAULT_COST_PARAMS: dict[str, CostParams] = dict(_DEFAULTS)


def get_cost_params(
    instrument: str, registry: dict[str, CostParams] | None = None
) -> CostParams:
    """Return cost params for ``instrument`` from ``registry`` (defaults if omitted)."""
    table = registry if registry is not None else DEFAULT_COST_PARAMS
    try:
        return table[instrument]
    except KeyError as exc:
        raise CostError(f"no cost parameters for instrument {instrument!r}") from exc
