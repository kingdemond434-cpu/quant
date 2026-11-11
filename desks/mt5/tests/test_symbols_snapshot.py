"""The broker's full symbol list: snapshot rows, diff kinds, registry merge, BARS_STATE label."""
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research import bars_state as B
from research import expand_universe as E

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 11, 11, 13, 0, tzinfo=UTC)
Q = 1767172440  # 2025-12-31T09:14:00Z


def sym(name, mode=4, path="Forex\\Majors\\X", exp=0, t=Q, visible=True, select=True):
    return SimpleNamespace(name=name, path=path, trade_mode=mode, expiration_time=exp,
                           visible=visible, select=select, time=t)


def test_snapshot_rows_cover_disabled_symbols_with_utc_times():
    rows = E.snapshot_rows([sym("UST10Y", 0, "Bonds\\UST10Y"), sym("EURUSD", t=0)])
    assert [r["name"] for r in rows] == ["EURUSD", "UST10Y"]
    ust = rows[1]
    assert ust == {"name": "UST10Y", "path": "Bonds\\UST10Y", "asset_class": "Bonds",
                   "trade_mode": 0, "expiration_time": None, "visible": True, "select": True,
                   "time": "2025-12-31T09:14:00+00:00"}
    assert rows[0]["time"] is None
    doc = E.build_snapshot(rows, NOW)
    assert doc["taken_at_utc"] == "2026-11-11T12:00:00+00:00"
    assert doc["by_trade_mode"] == {"0": 1, "4": 1}


def test_diff_kinds():
    prev = E.snapshot_rows([sym("A"), sym("B"), sym("C", 0), sym("D", exp=100), sym("GONE")])
    cur = E.snapshot_rows([sym("A"), sym("B", 0), sym("C", 4), sym("D", exp=200), sym("NEW")])
    got = {(c["kind"], c["symbol"]) for c in E.diff_snapshots(prev, cur, "t")}
    assert got == {("disabled", "B"), ("enabled", "C"), ("expiry_changed", "D"),
                   ("listed", "NEW"), ("delisted", "GONE")}
    dis = next(c for c in E.diff_snapshots(prev, cur, "t") if c["kind"] == "disabled")
    assert dis == {"kind": "disabled", "symbol": "B", "from": 4, "to": 0, "at": "t"}


def test_first_run_writes_baseline_then_diffs(tmp_path):
    snap, ch = tmp_path / "s.json", tmp_path / "c.jsonl"
    r = E.write_symbols_snapshot([sym("A"), sym("B")], NOW, snapshot=snap, changes=ch)
    assert r["diff"] == "baseline"
    lines = [json.loads(x) for x in ch.read_text().splitlines()]
    assert [x["kind"] for x in lines] == ["baseline"]
    assert json.loads(snap.read_text())["n_symbols"] == 2
    E.write_symbols_snapshot([sym("A"), sym("B", 0)], LATER, snapshot=snap, changes=ch)
    lines = [json.loads(x) for x in ch.read_text().splitlines()]
    assert [x["kind"] for x in lines] == ["baseline", "disabled"]


def test_unreadable_prior_skips_diff_never_floods_listed(tmp_path):
    snap, ch = tmp_path / "s.json", tmp_path / "c.jsonl"
    snap.write_text("{not json")
    r = E.write_symbols_snapshot([sym("A"), sym("B")], NOW, snapshot=snap, changes=ch)
    assert r["changes"] == 0 and "skipped" in r["diff"]
    assert not ch.exists()
    assert "skipped" in json.loads(snap.read_text())["diff"]


def test_empty_terminal_list_writes_nothing(tmp_path):
    snap, ch = tmp_path / "s.json", tmp_path / "c.jsonl"
    E.write_symbols_snapshot([sym("A")], NOW, snapshot=snap, changes=ch)
    before = snap.read_text()
    assert E.write_symbols_snapshot([], LATER, snapshot=snap, changes=ch)["written"] is False
    assert snap.read_text() == before


def test_registry_merge_disabled_then_reenabled_never_shrinks():
    reg = {"UST10Y": {"symbol": "UST10Y", "trade_mode": 3, "tick_value": 0.08},
           "EURUSD": {"symbol": "EURUSD"}, "OLDSYM": {"symbol": "OLDSYM"}}
    n = len(reg)
    out = E.merge_broker_status(reg, [sym("UST10Y", 0), sym("EURUSD")], NOW)
    assert len(reg) == n and set(reg) == {"UST10Y", "EURUSD", "OLDSYM"}
    u = reg["UST10Y"]
    assert u["broker_trade_mode"] == 0 and u["quoted"] is False and u["tradeable"] is False
    assert u["last_quote_utc"] == "2025-12-31T09:14:00+00:00"
    assert u["not_quoted_seen_at"] == NOW.isoformat(timespec="seconds")
    assert u["tick_value"] == 0.08            # merged, never replaced
    assert reg["OLDSYM"]["listed"] is False
    assert "quoted" not in reg["EURUSD"]
    assert out["not_quoted"] == ["UST10Y"] and out["unlisted"] == ["OLDSYM"]
    # second sighting keeps the first not_quoted_seen_at
    E.merge_broker_status(reg, [sym("UST10Y", 0), sym("EURUSD")], LATER)
    assert u["not_quoted_seen_at"] == NOW.isoformat(timespec="seconds")
    # the broker re-enables it, and OLDSYM returns
    out = E.merge_broker_status(reg, [sym("UST10Y", 4), sym("EURUSD"), sym("OLDSYM")], LATER)
    assert u["quoted"] is True and u["broker_trade_mode"] == 4 and u["tradeable"] is True
    assert reg["OLDSYM"]["listed"] is True
    assert out["requoted"] == ["UST10Y"] and out["relisted"] == ["OLDSYM"]
    assert len(reg) == n


def test_registry_merge_ignores_an_empty_symbol_list():
    reg = {"A": {"symbol": "A"}}
    E.merge_broker_status(reg, [], NOW)
    assert reg == {"A": {"symbol": "A"}}


def test_main_writes_snapshot_and_keeps_disabled_registry_row(tmp_path, monkeypatch):
    universe = tmp_path / "universe"
    universe.mkdir()
    reg = universe / "universe.json"
    reg.write_text(json.dumps({"UST10Y": {"symbol": "UST10Y", "trade_mode": 3},
                               "EURUSD": {"symbol": "EURUSD"}}))
    fake = SimpleNamespace(initialize=lambda: True, shutdown=lambda: None,
                           symbols_get=lambda: [sym("UST10Y", 0, "Bonds\\UST10Y")],
                           symbol_select=lambda *a: True, symbol_info=lambda *a: None,
                           TIMEFRAME_H1=1)
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    monkeypatch.setattr(E, "UNIVERSE", universe)
    monkeypatch.setattr(E, "REGISTRY", reg)
    monkeypatch.setattr(E, "REPORT", tmp_path / "report.json")
    monkeypatch.setattr(E, "SNAPSHOT", universe / "symbols_snapshot.json")
    monkeypatch.setattr(E, "CHANGES", universe / "symbols_changes.jsonl")
    monkeypatch.setattr(E, "_traded_symbols", lambda: set())
    assert E.main() == 0
    snap = json.loads((universe / "symbols_snapshot.json").read_text())
    assert [r["name"] for r in snap["symbols"]] == ["UST10Y"]
    out = json.loads(reg.read_text())
    assert set(out) == {"UST10Y", "EURUSD"}
    assert out["UST10Y"]["quoted"] is False and out["UST10Y"]["trade_mode"] == 3
    assert out["EURUSD"]["listed"] is False


def test_bars_state_labels_not_quoted_symbols(tmp_path, monkeypatch):
    universe = tmp_path / "universe"
    universe.mkdir()
    (universe / "universe.json").write_text(json.dumps(
        {"UST10Y": {"quoted": False}, "EURUSD": {"quoted": True}}))
    rows = {"UST10Y": {"symbol": "UST10Y", "timeframe": "H1", "status": "MEASURED",
                       "last_bar_time": "2099-01-01T00:00:00", "age_h": 0.1,
                       "mtime_age_h": 0.1},
            "EURUSD": {"symbol": "EURUSD", "timeframe": "H1", "status": "MEASURED",
                       "last_bar_time": "2026-11-11T10:00:00", "age_h": 2.0,
                       "mtime_age_h": 1.0}}
    for s in rows:
        (universe / f"{s}_H1.parquet").write_bytes(b"x")
    monkeypatch.setattr(B, "_bar_row", lambda path, sym, tf, now: dict(rows[sym]))
    doc = B.measure(universe=universe, ticks=tmp_path / "ticks",
                    tape_state=tmp_path / "none.json", now=NOW)
    by = {r["symbol"]: r for r in doc["bars"]}
    assert by["UST10Y"]["feed_status"] == B.NOT_QUOTED
    assert "feed_status" not in by["EURUSD"]
    assert doc["summary"]["not_quoted_by_broker"] == ["UST10Y"]
    assert doc["summary"]["newest_bar_time"] == "2026-11-11T10:00:00"
    assert doc["summary"]["newest_bar_file_mtime_age_h"] == 1.0
