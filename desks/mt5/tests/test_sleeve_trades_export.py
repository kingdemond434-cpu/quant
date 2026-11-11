"""The per-sleeve per-trade R export (BACKLOG 2026-11-10, Max-growth): measured trades only,
unmeasured ones counted not zeroed, nothing but the public-safe columns leaves."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from research import decay_monitor as D  # noqa: E402


def _row(sleeve, r, days_ago=1, **kw):
    t = (datetime.now(tz=UTC) - timedelta(days=days_ago)).isoformat()
    base = {"time": t, "sleeve": sleeve, "symbol": "XAUUSD", "r_multiple": r,
            "risk_quote": 5.0, "account_key": "k1", "server": "FusionMarkets-Live",
            "login": 123456, "pl_quote": 1.0}
    base.update(kw)
    return json.dumps(base)


def test_export_groups_filters_and_counts(tmp_path, monkeypatch):
    led = tmp_path / "live_ledger.jsonl"
    led.write_text("\n".join([
        _row("a", 1.0), _row("a", -0.5), _row("b", 2.0),
        _row("a", 0.0, r_unreconstructible=True),
        _row("b", 0.0, risk_quote=0),
        _row("b", "x"),
        _row("a", 3.0, days_ago=200),
        "{broken",
    ]) + "\n", "utf-8")
    monkeypatch.setattr(D, "LEDGER", led)
    out = tmp_path / "SLEEVE_TRADES.json"
    D.export_sleeve_trades(out)
    doc = json.loads(out.read_text("utf-8"))
    assert doc["ledger_state"] == "READ"
    assert doc["rows"] == 3
    assert doc["excluded"] == {"unreconstructible": 1, "risk_quote_le_0": 1, "no_numeric_r": 1,
                               "bad_json": 1, "older_than_window": 1}
    ri = doc["columns"].index("r_multiple")
    assert [t[ri] for t in doc["sleeves"]["a"]] == [1.0, -0.5]
    assert doc["summary"]["a"]["n"] == 2 and doc["summary"]["b"]["exp_r"] == 2.0
    assert "login" not in doc["columns"] and "123456" not in out.read_text("utf-8")


def test_absent_ledger_is_declared(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "LEDGER", tmp_path / "none.jsonl")
    doc = D.export_sleeve_trades(tmp_path / "o.json")
    assert doc["ledger_state"] == "NO_LEDGER" and doc["rows"] == 0


def test_row_cap_keeps_newest_and_declares_cut(tmp_path, monkeypatch):
    led = tmp_path / "l.jsonl"
    led.write_text("\n".join(_row("a", float(i)) for i in range(5)) + "\n", "utf-8")
    monkeypatch.setattr(D, "LEDGER", led)
    monkeypatch.setattr(D, "EXPORT_MAX_ROWS", 2)
    doc = D.export_sleeve_trades(tmp_path / "o.json")
    ri = doc["columns"].index("r_multiple")
    assert doc["rows_cut_oldest"] == 3 and [t[ri] for t in doc["sleeves"]["a"]] == [3.0, 4.0]
