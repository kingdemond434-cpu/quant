"""THE ORGANS THAT WRITE COMMITTED STATE MUST NOT STAMP THE LIVE LOGIN INTO IT.

`account_state.json` (ops/publish_account_state.py), `cost_truth_quotes.json` and the rendered
`docs/research/COST_TRUTH.md` (desks/mt5/research/cost_truth.py) and the spread tape's snapshot
(desks/mt5/research/fusion_spread_tape.py) are all written on the trading box and committed by it.
Editing the committed copies on origin does nothing: the box's next push reverts them. The fix is
the WRITER, and this pins it -- a fake terminal reports a placeholder login and the test asserts
the placeholder appears nowhere in what the organ writes, while everything else it published
(venue, server, currency, equity) is still there. Nothing here trades or reads a real account.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "desks" / "mt5"), str(ROOT / "desks" / "mt5" / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: A placeholder, never the real login: the fence test forbids that anywhere in a tracked file.
FAKE_LOGIN = 5551234


def _fake_mt5() -> types.ModuleType:
    acct = types.SimpleNamespace(
        login=FAKE_LOGIN, company="Fusion Markets Pty Ltd", server="FusionMarkets-Live",
        currency="EUR", balance=100.0, equity=101.5, margin_free=99.0, margin_mode=2,
        leverage=500)
    m = types.ModuleType("MetaTrader5")
    m.TIMEFRAME_M1 = 1  # type: ignore[attr-defined]
    for name, value in {
        "initialize": lambda *a, **k: True, "shutdown": lambda *a, **k: None,
        "last_error": lambda *a, **k: (0, "ok"), "account_info": lambda *a, **k: acct,
        "terminal_info": lambda *a, **k: types.SimpleNamespace(
            name="t", connected=True, build=1),
        "history_deals_get": lambda *a, **k: (), "positions_get": lambda *a, **k: (),
        "symbol_info": lambda *a, **k: None, "symbol_info_tick": lambda *a, **k: None,
        "copy_rates_from_pos": lambda *a, **k: None,
    }.items():
        setattr(m, name, value)
    return m


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_publish_account_state_withholds_the_login(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "MetaTrader5", _fake_mt5())
    mod = _load("publish_account_state_under_test", ROOT / "ops" / "publish_account_state.py")
    out = tmp_path / "account_state.json"
    monkeypatch.setattr(mod, "OUT", out)
    assert mod.main() == 0
    text = out.read_text(encoding="utf-8")
    assert str(FAKE_LOGIN) not in text
    rec = json.loads(text)
    assert "login" not in rec and rec["login_withheld"] is True
    assert rec["server"] == "FusionMarkets-Live" and rec["equity"] == 101.5


def test_cost_truth_snapshot_and_page_withhold_the_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "MetaTrader5", _fake_mt5())
    import cost_truth as CT

    snap = CT.terminal_snapshot([], budget_s=1.0, bars_cap=1)
    assert str(FAKE_LOGIN) not in json.dumps(snap, default=str)
    assert snap["account"]["login_withheld"] is True
    assert snap["account"]["server"] == "FusionMarkets-Live"
    # An older report that still carries a login must not reprint it on the derived page.
    page = CT.render_md({"account": {"login": FAKE_LOGIN, "company": "Fusion Markets Pty Ltd",
                                     "server": "FusionMarkets-Live", "currency": "EUR"}})
    assert str(FAKE_LOGIN) not in page and "FusionMarkets-Live" in page


def test_spread_tape_snapshot_withholds_the_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "MetaTrader5", _fake_mt5())
    import fusion_spread_tape as FST

    snap = FST.live_snapshot([])
    assert str(FAKE_LOGIN) not in json.dumps(snap, default=str)
    assert snap["account"]["login_withheld"] is True
