"""K4: the daily P&L explain splits each account's realised P&L and publishes no money."""
from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path

from research import pnl_explain as pe

NOW = datetime(2026, 11, 17, 12, tzinfo=UTC)


def _row(**kw):
    base = {"time": "2026-11-16T10:00:00+00:00", "exit_time": "2026-11-16T09:59:00+00:00",
            "symbol": "XAUUSD", "entry_side": 0, "side": 1, "volume": 0.01,
            "contract_size": 100.0, "entry_price": 4000.0, "fill_price": 4010.0, "sl": 3990.0,
            "risk_quote": 10.0, "commission": -0.02, "swap": -0.05, "exit_fee": 0.0,
            "entry_cost_allocated": -0.02, "r_multiple": 0.991, "entry_order": 7,
            "account_key": "sha256:abc", "server": "Broker-Live", "account_kind": "live"}
    base.update(kw)
    base["pl_quote"] = kw.get("pl_quote", 10.0 - 0.02 - 0.05 - 0.02)
    return base


def test_a_long_with_a_bad_fill_splits_and_sums_to_net() -> None:
    intents = [{"ticket": 7, "side": "buy_stop", "intended": 3999.0}]
    doc = pe.build([_row()], intents, NOW)
    day = doc["accounts"]["live-1"]["days"]["2026-11-16"]
    b = day["bps"]
    assert day["status"] == "MEASURED" and day["split"] == 1
    assert b["slippage"] < 0 and b["signal"] > 0 and b["commission"] < 0 and b["swap"] < 0
    total = sum(b[k] for k in ("signal", "slippage", "commission", "swap", "fx_conversion",
                               "price_unsplit"))
    assert abs(total - b["net"]) < 0.05
    assert abs(b["fx_conversion"]) < 0.05  # account currency == quote currency here
    assert abs(sum(day["share"].values()) - 1.0) < 1e-3


def test_no_intent_is_unsplit_and_no_stop_is_unmeasured() -> None:
    doc = pe.build([_row(), _row(sl=None, entry_order=8)], [], NOW)
    day = doc["accounts"]["live-1"]["days"]["2026-11-16"]
    assert day["status"] == "PARTIAL" and day["unmeasured"] == 1 and day["split"] == 0
    assert day["bps"]["signal"] is None and day["bps"]["price_unsplit"] > 0
    empty = pe.build([_row(sl=None)], [], NOW)
    assert empty["status"] == "UNMEASURED"


def test_nothing_identifying_or_monetary_is_published(tmp_path: Path) -> None:
    led, out = tmp_path / "l.jsonl", tmp_path / "o.json"
    led.write_text(json.dumps(_row(pl_quote=1234.56)) + "\n", "utf-8")
    assert pe.main(["--ledger", str(led), "--intents", str(tmp_path / "none"),
                    "--out", str(out)]) == 0
    blob = out.read_text("utf-8")
    for leak in ("sha256:abc", "Broker-Live", "1234.56", "4010", "4000.0"):
        assert leak not in blob, leak
    assert set(json.loads(blob)["accounts"]) == {"live-1"}


def test_report_only_it_imports_no_gateway_sizing_or_orders() -> None:
    tree = ast.parse(Path(pe.__file__).read_text("utf-8"))
    mods = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    mods |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(m.startswith("mt5desk") or "sizing" in m or "allocator" in m for m in mods)
