"""Which wallet the sleeves trade from -- the switch that stops a transfer from silencing a book.

THE FAILURE THIS PREVENTS. Binance treats spot and cross-margin as separate wallets with separate
balances. Both live sleeves imported the spot connector directly, so moving capital to margin would
have left them working perfectly and doing nothing: the executor reading ~$0 of equity and placing
no orders, the sleeve finding no free quote and refusing all eleven rules for insufficient funds.

No error, no alarm. A book that has simply stopped, looking exactly like a quiet market.
"""

from __future__ import annotations

import pytest

from libs.execution import binance_margin_live, binance_spot_live
from libs.execution.wallet import WALLETS, connector, is_margin


def test_EACH_NAME_ROUTES_TO_ITS_OWN_CONNECTOR() -> None:
    assert connector("spot") is binance_spot_live
    assert connector("margin") is binance_margin_live
    assert set(WALLETS) == {"spot", "margin"}


def test_AN_UNKNOWN_WALLET_RAISES_RATHER_THAN_DEFAULTING() -> None:
    """A typo'd --wallet silently trading the wrong wallet is the exact failure this module
    exists to prevent, and a default would reintroduce it where it is easiest to make."""
    for bad in ("margn", "", "MARGIN_ACCOUNT", "futures"):
        with pytest.raises(ValueError, match="unknown wallet"):
            connector(bad)


def test_BOTH_CONNECTORS_PRESENT_THE_INTERFACE_THE_ORDER_PATH_USES() -> None:
    """The shared placement primitive calls these by name. A connector missing one would fail at
    the venue call rather than at import -- i.e. with real money in flight."""
    for mod in (binance_spot_live, binance_margin_live):
        for fn in ("is_armed", "balances", "place_market_quote", "place_stop_loss_limit"):
            assert callable(getattr(mod, fn, None)), f"{mod.__name__} is missing {fn}"


def test_THE_MARGIN_STOP_REPAYS_THE_LOAN() -> None:
    """A stop that sells the position and leaves the loan outstanding has removed the asset and
    kept the liability: the margin level barely improves and interest accrues on a book holding
    nothing. On a levered position the repayment IS the protection."""
    import inspect
    src = inspect.getsource(binance_margin_live.place_stop_loss_limit)
    assert "AUTO_REPAY" in src


def test_IS_MARGIN_IS_NOT_A_SUBSTRING_MATCH() -> None:
    assert is_margin("margin") and is_margin(" MARGIN ")
    assert not is_margin("spot") and not is_margin("marginal_thing")


def test_BOTH_RUNNERS_EXPOSE_THE_SWITCH() -> None:
    """A wallet-aware connector nobody can select is the same defect one layer down."""
    from pathlib import Path
    for f in ("scripts/run_spot_executor.py", "scripts/run_discretionary_live.py"):
        src = Path(f).read_text("utf-8")
        assert '"--wallet"' in src, f"{f} cannot be pointed at the margin wallet"
        assert "connector(args.wallet)" in src


def test_MARKET_DATA_IS_NOT_ROUTED_BY_WALLET() -> None:
    """There is one BNBUSDC market, not a spot one and a margin one. Prices and filters come from
    the public endpoints either way; only balances and orders follow the wallet."""
    from pathlib import Path
    src = Path("scripts/run_spot_executor.py").read_text("utf-8")
    assert "px = market.prices()" in src and "filters = market.exchange_filters()" in src
    assert "held = live.balances()" in src
