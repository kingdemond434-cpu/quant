"""A paused gateway publishes a read-only account reading, so the ruin rail is never stuck
judging a frozen equity number (Fusion, frozen at EUR 266.01 from 2026-10-30)."""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Off the box MetaTrader5 is absent: a stub stands in for the import only and is removed at
# once, so tests that `importorskip("MetaTrader5")` still skip. Every call below is faked.
_STUBBED = False
try:
    import MetaTrader5  # noqa: F401
except ImportError:
    sys.modules["MetaTrader5"] = types.ModuleType("MetaTrader5")
    _STUBBED = True
try:
    from mt5desk import gateway
finally:
    if _STUBBED:
        sys.modules.pop("MetaTrader5", None)


class FakeMt5:
    def __init__(self, acc, positions=(), orders=()):
        self.acc = acc
        self.positions, self.orders = list(positions), list(orders)
        self.sent: list = []

    def account_info(self):
        return self.acc

    def positions_total(self):
        return len(self.positions)

    def orders_total(self):
        return len(self.orders)

    def order_send(self, req):  # pragma: no cover - must never be called
        self.sent.append(req)
        raise AssertionError("a paused pass must not send orders")


@pytest.fixture
def paused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    state = tmp_path / "gateway_state.json"
    state.write_text(json.dumps({"equity": 266.01, "last_reconcile": "2026-10-30T20:50:00+00:00",
                                 "armed": True}), encoding="utf-8")
    monkeypatch.setattr(gateway, "STATE", state)
    monkeypatch.setattr(gateway, "gateway_paused", lambda: True)
    monkeypatch.setattr(gateway, "connect", lambda: True)
    monkeypatch.setattr(gateway, "log", lambda msg: None)
    return state


def test_paused_pass_publishes_equity_but_not_reconcile(paused: Path, monkeypatch) -> None:
    fake = FakeMt5(SimpleNamespace(equity=812.4, margin_free=800.0), positions=[1], orders=[1, 2])
    monkeypatch.setattr(gateway, "mt5", fake)
    gateway.main()
    st = json.loads(paused.read_text(encoding="utf-8"))
    assert st["equity"] == 812.4 and st["margin_free"] == 800.0
    assert st["reading_source"] == "paused_read_only" and st["reading_at"]
    assert st["reading_positions_total"] == 1 and st["reading_orders_total"] == 2
    # no management ran, so the stale-gateway clock must still read the truth
    assert st["last_reconcile"] == "2026-10-30T20:50:00+00:00"
    assert st["armed"] is True and fake.sent == []


def test_unreadable_account_leaves_the_state_untouched(paused: Path, monkeypatch) -> None:
    monkeypatch.setattr(gateway, "mt5", FakeMt5(None))
    before = paused.read_text(encoding="utf-8")
    gateway.main()
    assert paused.read_text(encoding="utf-8") == before


def test_disconnected_terminal_is_unmeasured(paused: Path, monkeypatch) -> None:
    monkeypatch.setattr(gateway, "connect", lambda: False)
    assert gateway.publish_paused_reading().startswith("paused reading UNMEASURED")
