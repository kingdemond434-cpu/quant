"""K4: the daily P&L explain splits the book's realised P&L and publishes no money or account."""
from __future__ import annotations

import ast
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from research import pnl_explain as pe

NOW = datetime(2026, 11, 17, 12, tzinfo=UTC)
DAY = "2026-11-16"
#: Account currency per quote unit the venue applied: a EUR account trading a USD-quoted symbol.
RATE = 0.9


def _row(**kw):
    base = {"time": "2026-11-16T10:00:00+00:00", "exit_time": "2026-11-16T09:59:00+00:00",
            "symbol": "XAUUSD", "entry_side": 0, "side": 1, "volume": 0.01,
            "contract_size": 100.0, "entry_price": 4000.0, "fill_price": 4010.0, "sl": 3990.0,
            "risk_quote": 10.0 * RATE, "commission": -0.02, "swap": -0.05, "exit_fee": 0.0,
            "entry_cost_allocated": -0.02, "net_cost_status": "MEASURED",
            "r_multiple": 0.991, "entry_order": 7,
            "account_key": "sha256:abc", "server": "Broker-Live", "account_kind": "live"}
    base.update(kw)
    cost = sum(v for v in (base["commission"], base["swap"], base["exit_fee"],
                           base["entry_cost_allocated"]) if v is not None)
    base["pl_quote"] = kw.get("pl_quote", 10.0 * RATE + cost)
    return base


def _components(b: dict) -> float:
    return sum(b[k] or 0.0 for k in ("signal", "slippage", "commission", "swap", "fx_conversion",
                                     "price_unsplit"))


def test_a_long_with_a_bad_fill_splits_and_sums_to_net() -> None:
    intents = [{"ticket": 7, "side": "buy_stop", "intended": 3999.0}]
    doc = pe.build([_row()], intents, NOW)
    day = doc["book"]["days"][DAY]
    b = day["bps"]
    assert doc["status"] == "MEASURED" and day["status"] == "MEASURED" and day["split"] == 1
    assert day["flags"] == {}
    assert b["slippage"] < 0 and b["signal"] > 0 and b["commission"] < 0 and b["swap"] < 0
    assert abs(_components(b) - b["net"]) < 0.05
    assert abs(b["fx_conversion"]) < 0.05  # the venue rate converts the move exactly here
    assert abs(sum(day["share"].values()) - 1.0) < 1e-3


def test_no_intent_is_unsplit_and_no_stop_is_unmeasured() -> None:
    doc = pe.build([_row(), _row(sl=None, entry_order=8)], [], NOW)
    day = doc["book"]["days"][DAY]
    assert day["status"] == "PARTIAL" and day["unmeasured"] == 1 and day["split"] == 0
    assert day["bps"]["signal"] is None and day["bps"]["price_unsplit"] > 0
    empty = pe.build([_row(sl=None)], [], NOW)
    assert empty["status"] == "UNMEASURED"


@pytest.mark.parametrize("missing", [
    {"entry_cost_allocated": None, "net_cost_status": "UNMEASURED_ENTRY_COST"},
    {"entry_cost_allocated": None},                           # a row from before the field
    {"net_cost_status": "UNMEASURED_ENTRY_COST"},             # the status alone is enough
])
def test_an_unmeasured_entry_cost_is_never_a_zero_and_never_measured(missing: dict) -> None:
    """MF2: the gateway writes entry_cost_allocated=None with UNMEASURED_ENTRY_COST and leaves
    the entry cost out of pl_quote. The row keeps its known costs, is PARTIAL, names the gap,
    and keeps its day and the report off MEASURED (L1.28a)."""
    row = _row(**missing)
    intents = [{"ticket": 7, "side": "buy", "intended": 4000.0}]
    ex = pe.explain_row(row, intents[0])
    assert ex["status"] == "PARTIAL" and ex["flags"] == ["UNMEASURED_ENTRY_COST"]
    # Commission + exit fee only: a null entry cost is not summed as 0 into a MEASURED row, and
    # a number beside an UNMEASURED_ENTRY_COST status is not summed at all.
    to_bps = 1e4 / (4000.0 * 0.01 * 100.0 * RATE)
    assert abs(ex["bps"]["commission"] - (-0.02) * to_bps) < 1e-9
    doc = pe.build([row], intents, NOW)
    day = doc["book"]["days"][DAY]
    assert day["status"] == "PARTIAL" and day["partial"] == 1
    assert day["flags"] == {"UNMEASURED_ENTRY_COST": 1}
    assert doc["status"] == "PARTIAL" and "1 partial" in doc["why"]


def test_the_quote_currency_rate_fallback_is_flagged_not_measured() -> None:
    """SF1: without tick value/size closed_trade_r sizes risk in the quote currency, so the venue
    rate is exactly 1 and all conversion lands in fx_conversion. That row is PARTIAL with
    RATE_QUOTE_FALLBACK, never MEASURED."""
    row = _row(risk_quote=10.0, pl_quote=9.0 - 0.09)  # risk at rate 1; P&L really in EUR
    ex = pe.explain_row(row, {"ticket": 7, "side": "buy", "intended": 4000.0})
    assert ex["status"] == "PARTIAL" and ex["flags"] == ["RATE_QUOTE_FALLBACK"]
    assert ex["bps"]["fx_conversion"] < -2  # the unmeasured conversion, parked as fx
    doc = pe.build([row], [{"ticket": 7, "side": "buy", "intended": 4000.0}], NOW)
    assert doc["book"]["days"][DAY]["flags"] == {"RATE_QUOTE_FALLBACK": 1}
    assert doc["status"] == "PARTIAL"
    # risk_quote is rounded to 6 dp on the ledger: still read as the fallback.
    assert pe.explain_row(_row(risk_quote=10.0000004), None)["flags"] == ["RATE_QUOTE_FALLBACK"]


def test_the_published_report_is_book_level_with_no_account(tmp_path: Path) -> None:
    """SF2: every account is pooled; the per-account detail goes only to the local file."""
    led, out, loc = tmp_path / "l.jsonl", tmp_path / "o.json", tmp_path / "acc.local.json"
    rows = [_row(pl_quote=1234.56),
            _row(account_key="sha256:def", server="Other-Live", entry_order=9),
            _row(account_key="sha256:ghi", server="Demo-Srv", account_kind="demo",
                 entry_order=10)]
    led.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    assert pe.main(["--ledger", str(led), "--intents", str(tmp_path / "none"),
                    "--out", str(out), "--local-out", str(loc)]) == 0
    blob = out.read_text("utf-8")
    for leak in ("sha256:", "Broker-Live", "Other-Live", "Demo-Srv", "1234.56", "4010",
                 "4000.0", "live-1", "live-2", "demo-1"):
        assert leak not in blob, leak
    assert not re.search(r'"accounts?"\s*:', blob)
    doc = json.loads(blob)
    assert doc["book"]["days"][DAY]["closed"] == 3 and doc["book"]["closed"] == 3
    local = json.loads(loc.read_text("utf-8"))
    assert set(local["accounts"]) == {"live-1", "live-2", "demo-1"}
    lblob = loc.read_text("utf-8")
    for leak in ("sha256:", "Broker-Live", "Other-Live", "Demo-Srv"):
        assert leak not in lblob, leak


def test_the_per_account_file_is_gitignored_and_never_published() -> None:
    repo = Path(pe.__file__).resolve().parents[3]
    rel = pe.LOCAL_OUT.relative_to(repo).as_posix()
    sync = (repo / "desks/mt5/scripts/sync_shadow_to_git.ps1").read_text("utf-8")
    # Named in a comment (why it is absent), never as a quoted path in any list.
    assert not re.search(r"[\"'][^\"'\n]*PNL_EXPLAIN_ACCOUNTS", sync)
    assert "desks/mt5/reports/PNL_EXPLAIN.json" in sync
    try:
        r = subprocess.run(["git", "check-ignore", "-q", "--no-index", rel], cwd=repo,
                           capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        pytest.skip("git unavailable")
    if r.returncode == 128:
        pytest.skip("not a git checkout")
    assert r.returncode == 0, f"{rel} is not gitignored"


def test_report_only_it_imports_no_gateway_sizing_or_orders() -> None:
    tree = ast.parse(Path(pe.__file__).read_text("utf-8"))
    mods = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    mods |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(m.startswith("mt5desk") or "sizing" in m or "allocator" in m for m in mods)
