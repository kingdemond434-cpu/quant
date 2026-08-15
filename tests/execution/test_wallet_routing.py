"""Which wallet the sleeves trade from -- the switch that stops a transfer from silencing a book.

THE FAILURE THIS PREVENTS. Binance treats spot and cross-margin as separate wallets with separate
balances. Both live sleeves imported the spot connector directly, so moving capital to margin would
have left them working perfectly and doing nothing: the executor reading ~$0 of equity and placing
no orders, the sleeve finding no free quote and refusing all eleven rules for insufficient funds.

No error, no alarm. A book that has simply stopped, looking exactly like a quiet market.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from libs.execution import binance_margin_live, binance_spot_live, wallet
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


# ------------------------------------------------------------------ where the money actually is
def _stub(monkeypatch: pytest.MonkeyPatch, spot: object, margin: object) -> None:
    """Point both connectors' `balances` at canned answers. A callable that RAISES stands for an
    unreadable wallet, which must never be reported as an empty one."""
    for mod, val in ((binance_spot_live, spot), (binance_margin_live, margin)):
        def _b(v: object = val) -> dict[str, float]:
            if isinstance(v, Exception):
                raise v
            return {"USDC": float(v)}          # type: ignore[arg-type]
        monkeypatch.setattr(mod, "balances", _b)


def test_IT_NAMES_THE_WALLET_HOLDING_THE_MONEY(monkeypatch: pytest.MonkeyPatch) -> None:
    """THE RUNTIME CHECK THIS MODULE'S HEADER DESCRIBED AND NOTHING PERFORMED. A sleeve pointed at
    an emptied wallet places no orders, raises nothing, and writes a row identical to a day when
    every target was already on side. Until this existed, the two were indistinguishable."""
    _stub(monkeypatch, spot=0.0, margin=812.40)
    msg = wallet.misplaced_capital("spot", "USDC")
    assert msg and "MARGIN WALLET" in msg and "812.40" in msg
    assert "--wallet margin" in msg, "the message must carry the fix, not just the diagnosis"
    assert wallet.misplaced_capital("margin", "USDC") is None, "the money IS in margin: no news"


def test_IT_STAYS_QUIET_WHEN_NEITHER_WALLET_CAN_FUND_A_TRADE(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Pointing at an equally empty wallet is noise. 'The book is out of capital' is the honest
    report, and this function is not the organ that makes it."""
    _stub(monkeypatch, spot=0.0, margin=3.0)
    assert wallet.misplaced_capital("spot", "USDC", min_notional=10.0) is None


def test_AN_UNREADABLE_WALLET_IS_NONE_AND_NEVER_ZERO(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zero is the measurement that the money is gone. None is the statement that nobody looked
    successfully. Collapsing the second into the first is how 'the key lost margin permission'
    comes to read as 'the account is empty' -- and it would then hunt for capital that is there."""
    _stub(monkeypatch, spot=0.0, margin=RuntimeError("-2015 invalid API-key"))
    loc = wallet.locate_capital("USDC")
    assert loc["balances"]["margin"] is None
    assert "-2015" in loc["errors"]["margin"]
    assert loc["richest"] == "spot", "only READABLE wallets may be ranked"
    # and with margin unreadable there is no evidence the cash is elsewhere, so it says nothing
    assert wallet.misplaced_capital("spot", "USDC") is None


def test_IT_READS_AND_NEVER_TRANSFERS() -> None:
    """No transfer surface exists on this path and none may be added: an organ that could move
    capital between wallets to 'fix' the mismatch would be a money path nobody armed."""
    src = Path(wallet.__file__).read_text("utf-8")
    for forbidden in ("margin/transfer", "sapi/v1/margin/transfer", "universalTransfer"):
        assert forbidden not in src, f"{forbidden} must never appear in the wallet selector"
