"""CRO K3: the account's leverage is kept from pass to pass and every change is named."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.ops import leverage_watch as lw

T0 = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)


def _obs(p: Path, lev: float | None, t: datetime, sent: list) -> dict:
    return lw.observe(p, lev, now=t, emit=lambda kind, **f: sent.append((kind, f)))


def test_first_reading_is_measured_and_a_cut_is_named(tmp_path: Path) -> None:
    p, sent = tmp_path / "ACCOUNT_LEVERAGE.json", []
    assert _obs(p, 500, T0, sent)["venues"]["fusion"]["verdict"] == "MEASURED"
    assert _obs(p, 500, T0 + timedelta(hours=1), sent)["venues"]["fusion"]["verdict"] == "MEASURED"
    assert sent == []
    doc = _obs(p, 100, T0 + timedelta(hours=2), sent)
    row = doc["venues"]["fusion"]
    assert row["verdict"] == "CHANGED" and row["leverage"] == 100.0
    assert row["changes"][-1] == {"at": (T0 + timedelta(hours=2)).isoformat(),
                                  "from": 500.0, "to": 100.0, "direction": "CUT"}
    assert sent == [("ACCOUNT_LEVERAGE_CHANGED", {"producer": "research/financing_lab.py",
                                                  "priority": 2, "venue": "fusion",
                                                  "from": 500.0, "to": 100.0,
                                                  "direction": "CUT"})]
    assert json.loads(p.read_text())["venues"]["fusion"]["leverage"] == 100.0


def test_an_unreadable_pass_is_never_a_change_and_ages_to_stale(tmp_path: Path) -> None:
    p, sent = tmp_path / "ACCOUNT_LEVERAGE.json", []
    assert _obs(p, None, T0, sent)["venues"]["fusion"]["verdict"] == "UNMEASURED"
    _obs(p, 500, T0, sent)
    for lev in (None, 0, -5):
        row = _obs(p, lev, T0 + timedelta(hours=2), sent)["venues"]["fusion"]
        assert row["leverage"] == 500.0 and row["verdict"] == "MEASURED"
    row = _obs(p, None, T0 + timedelta(hours=lw.STALE_AFTER_H + 1), sent)["venues"]["fusion"]
    assert row["verdict"] == "STALE" and sent == []


def test_the_published_file_names_no_account(tmp_path: Path) -> None:
    p = tmp_path / "ACCOUNT_LEVERAGE.json"
    lw.observe(p, 500, now=T0, emit=lambda *a, **k: None)
    text = p.read_text()
    for banned in ("login", "server", "account_number"):
        assert banned not in text


def test_the_lab_wires_it() -> None:
    # The kind is not in libs.ops.events.KINDS yet: events.py is money path the replay cannot
    # measure, so the vocabulary row rides on its own; emit() still writes it (unknown_kind).
    src = (Path(__file__).resolve().parents[2] / "desks" / "mt5" / "research"
           / "financing_lab.py").read_text(encoding="utf-8")
    assert "from libs.ops.leverage_watch import observe" in src
    assert 'live = acct.get("source") == "live terminal"' in src
    assert "symbol_margins(" in src


class _MT5:
    ORDER_TYPE_BUY, ORDER_TYPE_SELL = 0, 1

    def __init__(self, margin: float) -> None:
        self.margin = margin

    def symbol_info(self, sym: str) -> object | None:
        return None if sym == "NOPE" else type("I", (), {"trade_contract_size": 100.0})()

    def symbol_info_tick(self, sym: str) -> object:
        return type("T", (), {"ask": 4000.0, "bid": 3999.0})()

    def order_calc_margin(self, otype: int, sym: str, vol: float, px: float) -> float:
        return self.margin


def test_a_per_symbol_cut_is_named_without_an_account_change(tmp_path: Path) -> None:
    p, sent = tmp_path / "ACCOUNT_LEVERAGE.json", []
    rows = lw.symbol_margins(_MT5(2000.0), ["xauusd", "NOPE", "XAUUSD"])
    assert list(rows) == ["XAUUSD"] and rows["XAUUSD"]["effective_leverage"] == 200.0
    lw.observe(p, 500, now=T0, emit=lambda k, **f: sent.append(k), symbols=rows)
    small = lw.symbol_margins(_MT5(2200.0), ["XAUUSD"])         # +10%: not a change
    assert lw.observe(p, 500, now=T0 + timedelta(hours=1), emit=lambda k, **f: sent.append(k),
                      symbols=small)["venues"]["fusion"]["verdict"] == "MEASURED"
    cut = lw.symbol_margins(_MT5(4000.0), ["XAUUSD"])           # margin doubled: a CUT
    row = lw.observe(p, 500, now=T0 + timedelta(hours=2), emit=lambda k, **f: sent.append(k),
                     symbols=cut)["venues"]["fusion"]
    assert row["verdict"] == "CHANGED" and row["symbol_changes"][-1]["direction"] == "CUT"
    assert row["symbols"]["XAUUSD"]["effective_leverage"] == 100.0
    assert sent == ["SYMBOL_MARGIN_CHANGED"]
