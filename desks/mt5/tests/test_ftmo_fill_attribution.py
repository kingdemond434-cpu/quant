"""FTMO fill attribution: every fill joins its sleeve, signal and size rule or is listed
UNATTRIBUTED; a missing input is UNMEASURED, never 0."""
from __future__ import annotations

import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import ftmo_fill_attribution as fa  # noqa: E402

FIX = _DESK / "tests" / "fixtures" / "ftmo_first_fill"
NOW = datetime(2026, 11, 11, 10, 0, tzinfo=UTC)


def _point(monkeypatch: pytest.MonkeyPatch, tmp: Path) -> None:
    monkeypatch.setattr(fa, "PROP_LEDGER", tmp / "live_ledger_prop.jsonl")
    monkeypatch.setattr(fa, "INTENT_FILES", {"ftmo_executor": tmp / "ftmo_exec_intents.jsonl",
                                             "ftmo_follower": tmp / "ftmo_follower_intents.jsonl"})
    monkeypatch.setattr(fa, "ACCOUNT_STATE", tmp / "FTMO_ACCOUNT_STATE.json")
    monkeypatch.setattr(fa, "ALLOCATOR", tmp / "FTMO_ALLOCATOR.json")
    monkeypatch.setattr(fa, "SURVIVORS", (tmp / "UNIVERSAL_SURVIVORS.json",))
    monkeypatch.setattr(fa, "BAR_DIRS", (tmp / "bars",))


def test_nothing_readable_is_unmeasured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _point(monkeypatch, tmp_path)
    doc = fa.build(NOW)
    assert doc["status"] == fa.UNMEASURED
    assert doc["n_fills"] == fa.UNMEASURED
    assert doc["report_only"] is True and doc["consumer"] is None and doc["intended_consumer"]


def test_first_fill_attributes_to_its_sleeve(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    for f in FIX.iterdir():
        shutil.copy(f, tmp_path / f.name)
    _point(monkeypatch, tmp_path)
    doc = fa.build(NOW)
    assert doc["status"] == "OK" and doc["n_fills"] == 1 and doc["unattributed"] == []
    f = doc["fills"][0]
    assert f["attribution"] == "SYMBOL_SIDE_VOLUME"
    assert f["sleeve"] == "EURUSD.session_range_breakout"
    assert f["floating"] == -38.52
    assert f["size_rule"]["risk_frac"] == 0.004 and "lot_for_loss" in f["size_rule"]["rule"]
    e = f["expected"]
    assert e["expected_edge_r_per_trade"] == 0.187
    assert e["expected_net_r_per_trade"] == pytest.approx(0.166)
    assert e["hit_rate"] == fa.UNMEASURED          # the certificate carries none
    # no M1 bars: every horizon UNMEASURED, never 0; the position is still open
    assert all(f["markouts"][f"+{h}m"]["status"] == fa.UNMEASURED for h in fa.HORIZONS_MIN)
    assert f["markouts"]["to_close"]["status"] == fa.UNMEASURED
    assert f["vs_certificate"]["status"] == fa.UNMEASURED


def test_unmatched_fill_is_listed_never_dropped(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    _point(monkeypatch, tmp_path)
    (tmp_path / "FTMO_ACCOUNT_STATE.json").write_text(json.dumps(
        {"generated_at": NOW.isoformat(),
         "open_positions": [{"symbol": "USDJPY", "side": "short", "volume": 0.5,
                             "profit": 3.0}]}), "utf-8")
    doc = fa.build(NOW)
    assert doc["n_fills"] == 1 and doc["n_attributed"] == 0
    assert doc["unattributed"][0]["symbol"] == "USDJPY"
    assert doc["fills"][0]["attribution"] == fa.UNATTRIBUTED


def test_closed_fill_joins_by_order_id_and_scores_markouts(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pd = pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    for f in FIX.iterdir():
        shutil.copy(f, tmp_path / f.name)
    _point(monkeypatch, tmp_path)
    (tmp_path / "FTMO_ACCOUNT_STATE.json").write_text(json.dumps({"open_positions": []}), "utf-8")
    (tmp_path / "live_ledger_prop.jsonl").write_text(json.dumps(
        {"book": "ftmo", "lane": "ftmo_executor", "symbol": "EURUSD", "entry_side": 0,
         "entry_time": "2026-11-11T09:45:00+00:00", "exit_time": "2026-11-11T12:00:00+00:00",
         "entry_price": 1.0850, "sl": 1.0825, "volume": 1.25, "entry_order": 7001,
         "position_id": 7001, "r_multiple": 0.5}) + "\n", "utf-8")
    (tmp_path / "bars").mkdir()
    idx = pd.date_range("2026-11-11T09:45:00Z", periods=30, freq="1min")
    pd.DataFrame({"time": idx, "close": [1.0850 + 0.0001 * i for i in range(30)]}) \
        .to_parquet(tmp_path / "bars" / "EURUSD_M1.parquet")
    doc = fa.build(NOW)
    f = doc["fills"][0]
    assert f["attribution"] == "ORDER_ID"
    m = f["markouts"]
    assert m["+1m"]["r"] == pytest.approx(0.04)
    assert m["+15m"]["r"] == pytest.approx(0.6)
    assert m["+60m"]["status"] == fa.UNMEASURED     # the path stops before +60m
    assert m["to_close"]["r"] == 0.5
    assert f["vs_certificate"]["realised_minus_expected_net_r"] == pytest.approx(0.334)


def test_write_is_atomic(tmp_path: Path) -> None:
    out = tmp_path / "r" / "X.json"
    fa.write({"a": 1}, out)
    assert json.loads(out.read_text("utf-8")) == {"a": 1}
    assert not (out.parent / "X.json.tmp").exists()
