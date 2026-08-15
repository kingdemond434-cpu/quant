"""The first path on this desk that can be liquidated, fenced at every place it differs from spot.

Spot's safety properties are free: you hold what you paid for, and no third party can close your
position. Margin has none of them for free. Each test here corresponds to one property that had to
be re-established by hand, and each names the failure it prevents.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from libs.execution import binance_margin_live as m


def _arm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, margin_flag: bool = True) -> None:
    keyfile = tmp_path / "k.json"
    keyfile.write_text('{"key": "K", "secret": "S"}', "utf-8")
    monkeypatch.setattr(m, "_KEYFILE", keyfile)
    for name in ("_ENABLE_FLAG", "_VPS_MARKER"):
        f = tmp_path / name
        f.write_text("", "utf-8")
        monkeypatch.setattr(m, name, f)
    flag = tmp_path / "MARGIN_ENABLE"
    if margin_flag:
        flag.write_text("", "utf-8")
    monkeypatch.setattr(m, "_MARGIN_FLAG", flag)


def test_BORROWING_NEEDS_A_FOURTH_FILE_THAT_TRADING_DOES_NOT(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """'May this box trade' and 'may this box borrow' are different authorisations, and only the
    second can end the account. Spot's three-file contract must not be enough to reach leverage."""
    _arm(tmp_path, monkeypatch, margin_flag=False)
    armed, why = m.is_armed()
    assert armed is False
    assert "margin_enable_flag=False" in why
    _arm(tmp_path, monkeypatch, margin_flag=True)
    assert m.is_armed()[0] is True


def _live_strings(path: str) -> list[str]:
    """Every string literal the module can actually SEND, docstrings excluded.

    A plain grep would fail on the docstring that explains why the transfer endpoint is absent --
    and deleting that explanation to satisfy a test would remove the most useful line in the file.
    The property being asserted is about executable code, so the test reads executable code.
    """
    import ast
    tree = ast.parse(Path(path).read_text("utf-8"))
    doc_nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                doc_nodes.add(id(body[0].value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc_nodes]


def test_THERE_IS_NO_TRANSFER_OR_WITHDRAWAL_SURFACE() -> None:
    """Moving capital between wallets decides how much can be lost. It stays a principal act, and
    the guarantee is worth more as a test than as a promise in a docstring."""
    live = _live_strings("libs/execution/binance_margin_live.py")
    for forbidden in ("/sapi/v1/margin/transfer", "/sapi/v1/capital/withdraw",
                      "/sapi/v1/sub-account", "/sapi/v1/asset/transfer"):
        assert not any(forbidden in s for s in live), (
            f"{forbidden} appears in executable code -- this path has no transfer surface")


def test_THE_ABSENT_ENDPOINTS_ARE_STILL_EXPLAINED() -> None:
    """The docstring naming what is deliberately missing is the most useful line in the file, and
    the test above must not create pressure to delete it."""
    src = Path("libs/execution/binance_margin_live.py").read_text("utf-8")
    assert "/sapi/v1/margin/transfer" in src and "never will" in src


def test_A_MISSING_MARGIN_LEVEL_IS_NONE_NOT_A_NUMBER(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A default in either direction is a disaster in one of them: high waves every borrow
    through, low blocks a book from repaying. UNMEASURED must stay unmeasured (L1.28a)."""
    _arm(tmp_path, monkeypatch)
    monkeypatch.setattr(m, "account", lambda: {})
    assert m.margin_level() is None
    monkeypatch.setattr(m, "account", lambda: {"marginLevel": "0"})
    assert m.margin_level() is None
    monkeypatch.setattr(m, "account", lambda: {"marginLevel": "2.5"})
    assert m.margin_level() == 2.5


def test_AN_UNREADABLE_LEVEL_REFUSES_THE_BORROW(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE ONE THAT MATTERS MOST. An unknown distance to the liquidation line is not a safe one,
    and the only safe reading of 'unmeasured' on a borrowing path is no."""
    _arm(tmp_path, monkeypatch)
    monkeypatch.setattr(m, "margin_level", lambda: None)
    with pytest.raises(RuntimeError, match="UNREADABLE"):
        m.place_market_quote("BNBUSDC", "BUY", 100.0, cycle="c", borrow=True)


def test_A_THIN_MARGIN_LEVEL_REFUSES_THE_BORROW(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The level moves with the market, so the floor sits far above the liquidation line -- a check
    that passes at 1.15 has already failed by the time the order fills."""
    _arm(tmp_path, monkeypatch)
    monkeypatch.setattr(m, "margin_level", lambda: 1.4)
    with pytest.raises(RuntimeError, match="below the borrow floor"):
        m.place_market_quote("BNBUSDC", "BUY", 100.0, cycle="c", borrow=True)
    assert m._MIN_LEVEL_TO_BORROW > m.MARGIN_CALL_LEVEL > m.LIQUIDATION_LEVEL


def test_CLOSING_IS_NEVER_GATED_ON_THE_MARGIN_LEVEL(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE MIRROR, AND IT IS NOT SYMMETRIC. Closing RAISES the level. A rail that blocked it would
    trap a book above the liquidation line with no way down -- turning a margin call into a
    liquidation while every check reported working as designed."""
    _arm(tmp_path, monkeypatch)
    monkeypatch.setattr(m, "margin_level", lambda: 1.11)
    sent: dict[str, Any] = {}
    monkeypatch.setattr(m, "_signed", lambda p, params, method="GET": sent.update(params) or {})
    m.place_market_reduce("BNBUSDC", "SELL", 1.0, cycle="c")
    assert sent["sideEffectType"] == "AUTO_REPAY"


def test_NOT_BORROWING_IS_THE_DEFAULT(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A caller who forgets the argument must not end up in debt. NO_SIDE_EFFECT spends only what
    is already in the wallet."""
    _arm(tmp_path, monkeypatch)
    sent: dict[str, Any] = {}
    monkeypatch.setattr(m, "_signed", lambda p, params, method="GET": sent.update(params) or {})
    m.place_market_quote("BNBUSDC", "BUY", 50.0, cycle="c")
    assert sent["sideEffectType"] == "NO_SIDE_EFFECT"


def test_BORROWING_USES_THE_ORDERS_OWN_SIDE_EFFECT_NOT_A_SEPARATE_LOAN() -> None:
    """A /loan followed by an order is two operations that can succeed apart, leaving borrowed
    funds with no position against them -- paying interest on idle debt."""
    src = Path("libs/execution/binance_margin_live.py").read_text("utf-8")
    assert "/sapi/v1/margin/loan" not in src
    assert "MARGIN_BUY" in src and "AUTO_REPAY" in src


def test_LEVERAGE_IS_CAPPED_IN_CODE_AND_THE_CAP_IS_STATED() -> None:
    """A number that lives only in a caller's argument is one bad cron line from 10x."""
    usd, why = m.borrow_headroom(200.0, 10.0)
    assert usd == 200.0 * (m.MAX_LEVERAGE - 1.0)
    assert "CAPPED" in why and "3.00x" in why
    assert m.borrow_headroom(200.0, 1.0)[0] == 0.0


def test_LIABILITIES_INCLUDE_ACCRUED_INTEREST(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Interest is a real debt that grows hourly. A book that repays only principal never closes."""
    _arm(tmp_path, monkeypatch)
    monkeypatch.setattr(m, "account", lambda: {"userAssets": [
        {"asset": "USDC", "borrowed": "100.0", "interest": "0.5", "free": "0"},
        {"asset": "BNB", "borrowed": "0", "interest": "0", "free": "1.0"},
    ]})
    assert m.liabilities() == {"USDC": 100.5}


def test_BALANCES_ARE_FREE_NOT_NET(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Borrowed funds sitting unspent are spendable; netting them away understates what an order
    can use, and the executor would then under-fill the book it just sized."""
    _arm(tmp_path, monkeypatch)
    monkeypatch.setattr(m, "account", lambda: {"userAssets": [
        {"asset": "USDC", "free": "150.0", "borrowed": "100.0", "interest": "0"},
    ]})
    assert m.balances() == {"USDC": 150.0}


def test_AN_UNARMED_MODULE_PLACES_NOTHING(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _arm(tmp_path, monkeypatch, margin_flag=False)
    with pytest.raises(RuntimeError, match="not armed"):
        m.place_market_quote("BNBUSDC", "BUY", 10.0, cycle="c")


def test_A_BAD_SIDE_IS_REJECTED_BEFORE_THE_VENUE_SEES_IT(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _arm(tmp_path, monkeypatch)
    for fn in (lambda: m.place_market_quote("X", "LONG", 1.0, cycle="c"),
               lambda: m.place_market_reduce("X", "LONG", 1.0, cycle="c")):
        with pytest.raises(ValueError, match="BUY or SELL"):
            fn()
