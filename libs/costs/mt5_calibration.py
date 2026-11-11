"""Calibrate the Fusion cost model from REAL MT5 ``symbol_info`` (committee item T1).

The platform must report net-of-cost results, and the only honest cost inputs are the broker's
own: live spread, contract size, and swap. This module turns an MT5 ``symbol_info`` snapshot into
:class:`CostParams` and exposes the round-turn cost as a *fraction of notional* -- the form the
discovery backtests need to subtract on every position change.

Honest caveats baked in, not hidden:
  * Commission is NOT in ``symbol_info``; it is an asset-class prior (Fusion Zero ECN ~ $7/lot RT
    on FX/metals, spread-only on indices/crypto/equities). Override per real statements.
  * Slippage is a prior (a fraction of the live spread per side) until calibrated on real fills.
  * Swap is converted in the unit its swap_mode names; points -> money is exact only for
    USD-quoted symbols, and an annual-percent mode needs the caller's price.
The point is to make results *more* conservative than a flat fee, never less.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from libs.costs.errors import CostError
from libs.costs.params import CostParams
from libs.data.instruments import AssetClass

# Round-turn commission priors per lot, by asset class (account currency). Conservative defaults
# for a Fusion Zero ECN account; the FX/metal figure matches the ~$7/lot round turn they advertise.
_COMMISSION_PER_LOT: dict[AssetClass, float] = {
    AssetClass.FX: 7.0,
    AssetClass.METAL: 7.0,
    AssetClass.ENERGY: 7.0,
    AssetClass.SOFT: 7.0,
    AssetClass.INDEX: 0.0,
    AssetClass.CRYPTO: 0.0,
    AssetClass.EQUITY: 0.0,
}
# MT5 ENUM_SYMBOL_SWAP_MODE. THIS READ `_SWAP_MODE_POINTS = 0` UNTIL 2026-10-07: mode 0 is
# DISABLED and POINTS is 1, so every points symbol was taken as money and every disabled one as
# points -- and mode 5 (annual percent of notional, 138 of Fusion's 248 swap symbols) as money.
_SWAP_MODE_DISABLED = 0
_SWAP_MODE_POINTS = 1
_SWAP_MODE_DEPOSIT = 4
_SWAP_MODES_INTEREST = (5, 6)
_SWAP_MODES_REOPEN = (7, 8)
_SWAP_DAY_COUNT = 360.0


@runtime_checkable
class SymbolInfoLike(Protocol):
    """The subset of MT5 ``symbol_info`` fields the calibration needs (kept tiny for testing)."""

    spread: int                 # current spread in integer points
    point: float                # price increment of one point
    trade_contract_size: float  # units per lot
    swap_long: float
    swap_short: float
    swap_mode: int


def calibrate(
    symbol: str,
    info: SymbolInfoLike,
    *,
    asset_class: AssetClass,
    commission_per_lot: float | None = None,
    slippage_fraction_of_spread: float = 0.5,
    gap_risk_fraction: float = 0.0,
    price: float | None = None,
) -> CostParams:
    """Build :class:`CostParams` from a live ``symbol_info`` snapshot.

    ``spread_price`` is the full round-turn spread (spread points x point). Slippage per side is a
    conservative fraction of that spread. Commission falls back to the asset-class prior.
    """
    spread_price = float(info.spread) * float(info.point)
    if spread_price < 0:
        raise CostError(f"negative spread for {symbol!r}")
    contract_size = float(info.trade_contract_size)
    commission = (
        commission_per_lot if commission_per_lot is not None
        else _COMMISSION_PER_LOT.get(asset_class, 0.0)
    )
    slippage_per_side = spread_price * slippage_fraction_of_spread
    swap_long, swap_short = _swap_to_money(info, contract_size, price=price, symbol=symbol)
    return CostParams(
        instrument=symbol,
        contract_size=contract_size if contract_size > 0 else 1.0,
        commission_per_lot=commission,
        spread_price=spread_price,
        slippage_price_per_side=slippage_per_side,
        swap_long_per_lot_per_night=swap_long,
        swap_short_per_lot_per_night=swap_short,
        gap_risk_fraction=gap_risk_fraction,
    )


def _swap_to_money(info: SymbolInfoLike, contract_size: float, *, price: float | None = None,
                   symbol: str = "") -> tuple[float, float]:
    """Convert swap to cost-to-hold per lot per night (cost = positive), in the unit swap_mode
    names.

    MT5 swap is a credit when positive; our model wants a *cost*, so we negate.
      0 DISABLED -> 0; 1 POINTS and 7/8 REOPEN (+/- points) -> x point x contract size (exact
      for USD-quoted symbols); 4 DEPOSIT -> already money; 5/6 INTEREST -> annual percent of
      notional, x price x contract / 100 / 360 -- REQUIRES `price`.
    Anything else, or an interest mode without a price, raises CostError naming it: an
    unpriceable swap is UNMEASURED, never money and never zero.
    """
    mode = int(info.swap_mode)
    lo, sh = float(info.swap_long), float(info.swap_short)
    if mode == _SWAP_MODE_DISABLED:
        return (0.0, 0.0)
    if mode == _SWAP_MODE_POINTS or mode in _SWAP_MODES_REOPEN:
        scale = float(info.point) * contract_size
        return (-lo * scale, -sh * scale)
    if mode == _SWAP_MODE_DEPOSIT:
        return (-lo, -sh)
    if mode in _SWAP_MODES_INTEREST:
        if price is None or not price > 0:
            raise CostError(f"UNMEASURED: {symbol!r} swap_mode {mode} is an annual percent of "
                            "notional and needs a price")
        scale = float(price) * contract_size / 100.0 / _SWAP_DAY_COUNT
        return (-lo * scale, -sh * scale)
    raise CostError(f"UNMEASURED: {symbol!r} swap_mode {mode} has no money conversion here")


def round_turn_cost_fraction(params: CostParams, price: float) -> float:
    """Round-turn cost as a fraction of notional (spread + 2x slippage + commission).

    This is what a returns-space backtest subtracts each time the position turns over.
    """
    if price <= 0:
        raise CostError("price must be positive")
    notional_per_lot = params.contract_size * price
    spread_frac = params.spread_price / price
    slippage_frac = 2.0 * params.slippage_price_per_side / price
    commission_frac = params.commission_per_lot / notional_per_lot
    return spread_frac + slippage_frac + commission_frac


def per_side_cost_fraction(params: CostParams, price: float) -> float:
    """Half the round-turn fraction -- the cost charged on a single entry or exit."""
    return round_turn_cost_fraction(params, price) / 2.0


def cost_params_from_mt5(symbol: str, mt5, asset_class: AssetClass) -> CostParams:  # type: ignore[no-untyped-def]  # pragma: no cover - needs live terminal
    """Read live ``symbol_info`` from an initialized MT5 module and calibrate cost params."""
    mt5.symbol_select(symbol, True)
    info = mt5.symbol_info(symbol)
    if info is None:
        raise CostError(f"MT5 returned no symbol_info for {symbol!r}")
    return calibrate(symbol, info, asset_class=asset_class)
