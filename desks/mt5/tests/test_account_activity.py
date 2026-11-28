"""reports/ACCOUNT_ACTIVITY.json: when each account last traded, from rows shaped like the writers'.

Each fixture row copies the fields its writer emits (mt5desk/gateway.py, prop/ftmo_follower.py,
prop/ftmo_venue_reader.py, prop/e8_gold.py, prop/e8_executor.py, prop/e8_guard.py,
mt5desk/order_door.py, ops/publish_account_state.py, scripts/build_zentech_state.py).
"""
from __future__ import annotations

import ast
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from desks.mt5.research import account_activity as aa  # noqa: E402

NOW = datetime(2026, 11, 11, 4, 44, tzinfo=UTC)


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def _jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")


def _prop_fill(exit_t: datetime, *, volume: float = 0.07, entry_side: int = 0) -> dict[str, Any]:
    """prop/ftmo_follower.compose_fills (prop-fills-v1)."""
    return {"schema": "prop-fills-v1", "book": "ftmo", "venue": "mt5", "lane": "ftmo_follower",
            "recorded_at": _iso(exit_t), "time": _iso(exit_t), "sleeve": "gold_asia",
            "symbol": "XAUUSD", "entry_side": entry_side, "side": 1 - entry_side,
            "entry_time": _iso(exit_t - timedelta(hours=5)), "exit_time": _iso(exit_t),
            "volume": volume, "fill_price": 4100.0, "exit_reason": "sl", "position_id": 7}


def _ftmo_intent(at: datetime, status: str, **kw: Any) -> dict[str, Any]:
    """prop/ftmo_follower._record."""
    return {"at": _iso(at), "window": "asia", "lane": "ftmo", "status": status, **kw}


def _ftmo_state(*, balance: float, day_start: float, at: datetime = NOW) -> dict[str, Any]:
    """prop/ftmo_venue_reader: reports/FTMO_ACCOUNT_STATE.json."""
    return {"status": "OK", "generated_at": _iso(at), "phase": "challenge",
            "initial_balance": 100000.0, "balance": balance, "equity": balance,
            "day_start_balance": day_start, "days_traded": 3, "open_positions": []}


def _ftmo_desk(desk: Path, *, balance: float = 99666.72, day_start: float = 99666.72,
               sent_at: datetime | None = None) -> None:
    _jsonl(desk / "data/live_ledger_prop.jsonl",
           [_prop_fill(datetime(2026, 11, 1, 12, tzinfo=UTC), volume=0.05),
            _prop_fill(datetime(2026, 11, 3, 13, 10, 55, tzinfo=UTC), volume=0.07)])
    sent_at = sent_at or datetime(2026, 11, 10, 9, 6, 32, tzinfo=UTC)
    _jsonl(desk / "data/ftmo_follower_intents.jsonl", [
        _ftmo_intent(datetime(2026, 11, 3, 7, 30, tzinfo=UTC), "SENT", side="long",
                     kind="buy_stop", lot=0.07, retcode=10009),
        _ftmo_intent(datetime(2026, 11, 9, 23, 0, tzinfo=UTC), "SKIPPED", reason="wait",
                     why="E8's gold_asia has not been placed today"),
        _ftmo_intent(sent_at, "SENT", side="short", kind="sell_limit", lot=0.08,
                     retcode=10009),
        _ftmo_intent(datetime(2026, 11, 10, 11, tzinfo=UTC), "RAIL_BLOCKED",
                     rail="ftmo_follower", reason="e8_stale",
                     why="e8 gold state is 552s old (limit 540s)"),
        _ftmo_intent(datetime(2026, 11, 10, 15, tzinfo=UTC), "RAIL_BLOCKED",
                     rail="ftmo_follower", reason="e8_stale", why="pass report 568s old"),
        _ftmo_intent(datetime(2026, 11, 10, 23, 20, tzinfo=UTC), "SKIPPED", reason="wait",
                     why="E8's gold_asia has not been placed today"),
    ])
    _json(desk / "reports/FTMO_ACCOUNT_STATE.json",
          _ftmo_state(balance=balance, day_start=day_start))


# ------------------------------------------------------------------ newest fill and intent

def test_newest_fill_and_intent_are_picked(tmp_path: Path) -> None:
    _ftmo_desk(tmp_path)
    b = aa.ftmo(tmp_path, NOW)
    assert b["last_fill"]["ts"] == "2026-11-03T13:10:55+00:00"
    assert b["last_fill"]["source"] == "journal:live_ledger_prop.jsonl"
    assert b["last_fill"]["symbol"] == "XAUUSD"
    assert b["last_fill"]["side"] == "long" and b["last_fill"]["lots"] == 0.07
    assert b["last_intent"]["ts"] == "2026-11-10T23:20:00+00:00"
    assert b["last_intent"]["outcome"] == "SKIPPED"
    assert b["last_intent"]["reason"] == "wait"
    assert b["last_sent"]["ts"] == "2026-11-10T09:06:32+00:00"
    assert b["balance"] == 99666.72 and b["equity"] == 99666.72
    assert b["facts"] == "MEASURED"


def test_counts_in_the_last_24h(tmp_path: Path) -> None:
    _ftmo_desk(tmp_path)
    _jsonl(tmp_path / "data/live_ledger_prop.jsonl",
           [_prop_fill(NOW - timedelta(hours=30)), _prop_fill(NOW - timedelta(hours=2)),
            _prop_fill(NOW - timedelta(hours=1))])
    b = aa.ftmo(tmp_path, NOW)
    assert b["fills_24h"] == 2
    # 11-10 09:06 SENT, 11:00 and 15:00 RAIL_BLOCKED, 23:20 SKIPPED fall inside the 24h;
    # 11-09 23:00 SKIPPED and 11-03 SENT do not.
    assert b["intents_24h_by_outcome"] == {"RAIL_BLOCKED": 2, "SENT": 1, "SKIPPED": 1}


def test_fusion_intents_map_retcodes_and_skip_another_server(tmp_path: Path) -> None:
    """mt5desk/gateway._record_intent rows: `time`, `retcode`, and `status` only on a skip."""
    t = NOW - timedelta(hours=3)
    _jsonl(tmp_path / "data/order_intents.jsonl", [
        {"time": _iso(t), "sleeve": "gold_asia", "symbol": "XAUUSD", "side": "sell", "lot": 0.01,
         "retcode": 10009, "server": "FusionMarkets-Live"},
        {"time": _iso(t + timedelta(minutes=1)), "symbol": "XAUUSD", "retcode": 10016},
        {"time": _iso(t + timedelta(minutes=2)), "symbol": "XAUUSD", "status": "SKIPPED",
         "reason": "late_send"},
        {"time": _iso(t + timedelta(minutes=3)), "symbol": "XAUUSD", "retcode": 10009,
         "server": "FTMO-Server2"},
    ])
    _jsonl(tmp_path / "data/live_ledger.jsonl", [
        {"time": _iso(t), "exit_time": _iso(t - timedelta(minutes=5)), "symbol": "XAUUSD",
         "entry_side": 1, "side": 0, "volume": 0.01, "server": "FusionMarkets-Live"}])
    b = aa.fusion(tmp_path, tmp_path, NOW)
    assert b["intents_24h_by_outcome"] == {"REJECTED": 1, "SENT": 1, "SKIPPED": 1}
    assert b["last_fill"]["side"] == "short"
    assert b["last_fill"]["ts"] == _iso(t - timedelta(minutes=5))


# ------------------------------------------------------------------ stale journals

def test_a_journal_older_than_a_newer_sent_is_flagged(tmp_path: Path) -> None:
    _ftmo_desk(tmp_path)
    b = aa.ftmo(tmp_path, NOW)
    assert [s["file"] for s in b["journal_stale"]] == ["data/live_ledger_prop.jsonl"]
    s = b["journal_stale"][0]
    assert s["newest_row"] == "2026-11-03T13:10:55+00:00"
    assert s["newer_sent"] == "2026-11-10T09:06:32+00:00"
    assert s["confirmed_by_equity_step"] is False  # the balance has not moved today


def test_no_stale_flag_when_the_journal_is_newer(tmp_path: Path) -> None:
    _ftmo_desk(tmp_path, sent_at=datetime(2026, 11, 2, tzinfo=UTC))
    _jsonl(tmp_path / "data/ftmo_follower_intents.jsonl",
           [_ftmo_intent(datetime(2026, 11, 2, tzinfo=UTC), "SENT", lot=0.07)])
    assert aa.ftmo(tmp_path, NOW)["journal_stale"] == []


def test_e8_exit_fills_csv_is_stale_by_its_mtime(tmp_path: Path) -> None:
    """The csv has no writer in the repository: only its mtime bounds its newest row."""
    csvp = tmp_path / "data/e8_gold_exit_fills.csv"
    csvp.parent.mkdir(parents=True)
    csvp.write_text("a,b\n1,2\n", encoding="utf-8")
    old = datetime(2026, 10, 20, 23, 34, tzinfo=UTC).timestamp()
    os.utime(csvp, (old, old))
    sent = datetime(2026, 11, 10, 5, 1, 4, tzinfo=UTC)
    _jsonl(tmp_path / "data/e8_gold_intents.jsonl", [
        {"at": _iso(sent), "window": "asia", "side": "sell_stop", "price": 4108.24, "lot": 0.15,
         "status": "SENT", "order_id": 11, "armed": True},
        {"at": _iso(datetime(2026, 11, 10, 11, 1, tzinfo=UTC)), "window": "london_am",
         "status": "RAIL_BLOCKED", "rail": "principal_zero_pin",
         "why": "principal zero (gold asia only)", "armed": True}])
    _jsonl(tmp_path / "data/e8_intents.jsonl", [
        {"at": "2026-10-11T22:55:00+00:00", "armed": True, "symbol": "AUDCHF",
         "status": "STALE_SIGNAL", "why": "signal too old"}])
    _jsonl(tmp_path / "data/order_door_ledger.jsonl", [
        {"at": "2026-11-10T16:01:00+00:00", "caller": "e8_gold", "venue": "tradelocker",
         "kind": "stop", "action": "modify_stop", "args": [11], "kwargs": {},
         "outcome": "acknowledged"}])
    _json(tmp_path / "reports/E8_GOLD.json", {"at": _iso(NOW), "armed": True,
                                              "equity": 103227.24})
    _json(tmp_path / "data/e8_guard_state.json", {"day": "2026-11-11", "day_start": 103227.24,
                                                  "peak_equity": 103227.24,
                                                  "stood_down": False})
    b = aa.e8(tmp_path, NOW)
    st = b["journal_stale"]
    assert [s["file"] for s in st] == ["data/e8_gold_exit_fills.csv"]
    assert st[0]["newest_row_basis"].startswith("file mtime")
    assert st[0]["newer_sent"] == _iso(sent)
    assert b["last_intent"]["reason"] == "principal zero (gold asia only)"
    assert b["last_venue_write"]["action"] == "modify_stop"
    assert b["fills_24h"] is None and b["balance"] is None
    assert b["balance_unchanged_since"]["at_least_since"] == "server day 2026-11-11 start"
    assert b["facts"] == "PARTIAL"  # no E8 fill journal with a known schema


# ------------------------------------------------------------------ missing files

def test_missing_everything_is_unmeasured_never_quiet(tmp_path: Path) -> None:
    doc = aa.build(tmp_path, tmp_path, NOW)
    for name in ("fusion", "e8", "ftmo"):
        b = doc["accounts"][name]
        assert b["facts"] == "UNMEASURED", name
        assert b["missing"], name
        assert b["fills_24h"] is None, name  # unknown, never 0
        assert b["intents_24h_by_outcome"] is None, name
        assert b["last_fill"] is None


def test_a_missing_fill_journal_is_partial_with_null_counts(tmp_path: Path) -> None:
    _ftmo_desk(tmp_path)
    (tmp_path / "data/live_ledger_prop.jsonl").unlink()
    b = aa.ftmo(tmp_path, NOW)
    assert b["facts"] == "PARTIAL"
    assert b["missing"] == ["data/live_ledger_prop.jsonl"]
    assert b["fills_24h"] is None
    assert b["fills_24h_basis"].startswith("UNMEASURED")
    assert b["intents_24h_by_outcome"]  # what was read is still reported


def test_a_missing_intent_journal_is_partial(tmp_path: Path) -> None:
    _ftmo_desk(tmp_path)
    (tmp_path / "data/ftmo_follower_intents.jsonl").unlink()
    b = aa.ftmo(tmp_path, NOW)
    assert b["facts"] == "PARTIAL" and b["intents_24h_by_outcome"] is None
    assert b["last_intent"] is None


# ------------------------------------------------------------------ inferred fills

def test_a_balance_step_is_an_inferred_fill_and_says_so(tmp_path: Path) -> None:
    _ftmo_desk(tmp_path, balance=99900.0, day_start=99666.72,
               sent_at=datetime(2026, 11, 11, 0, 30, tzinfo=UTC))
    b = aa.ftmo(tmp_path, NOW)
    f = b["last_fill"]
    assert f["source"] == "inferred:equity_step"
    assert f["ts_is_upper_bound"] is True and f["ts"] == _iso(NOW)
    # FTMO's day starts at 00:00 Prague: 23:00 UTC in November
    assert f["ts_window"] == ["2026-11-10T23:00:00+00:00", _iso(NOW)]
    assert f["symbol"] is None  # the follower's intent rows carry no symbol
    assert f["lots"] == 0.08 and f["side"] == "short"
    assert "SENT at 2026-11-11T00:30:00+00:00" in f["detail_from_intent"]
    assert b["last_journaled_fill"]["source"] == "journal:live_ledger_prop.jsonl"
    assert b["journal_stale"][0]["confirmed_by_equity_step"] is True
    assert b["balance_unchanged_since"] is None
    assert any("no balance or equity history" in n for n in b["notes"])


def test_an_unmoved_balance_dates_balance_unchanged_since(tmp_path: Path) -> None:
    _ftmo_desk(tmp_path)
    u = aa.ftmo(tmp_path, NOW)["balance_unchanged_since"]
    assert u["at_least_since"] == "2026-11-10T23:00:00+00:00"
    assert "no balance history" in u["basis"]


def test_fusion_equity_history_step_and_account_switch(tmp_path: Path) -> None:
    """web/equity_history.jsonl (scripts/build_zentech_state._equity_history): at, equity."""
    t0 = NOW - timedelta(hours=10)
    _jsonl(tmp_path / "web/equity_history.jsonl", [
        {"at": _iso(t0), "equity": 600.0},
        {"at": _iso(t0 + timedelta(hours=1)), "equity": 600.0},
        {"at": _iso(t0 + timedelta(hours=2)), "equity": 612.5},
        {"at": _iso(t0 + timedelta(hours=3)), "equity": 612.5}])
    _jsonl(tmp_path / "data/order_intents.jsonl", [
        {"time": _iso(t0 + timedelta(minutes=30)), "symbol": "XAUUSD", "side": "buy",
         "lot": 0.01, "retcode": 10008}])
    _jsonl(tmp_path / "data/live_ledger.jsonl", [])
    _json(tmp_path / "data/account_state.json",
          {"updated_at": _iso(NOW), "server": "FusionMarkets-Live", "balance": 612.5,
           "equity": 612.5, "today_closed_pnl": 0.0})
    b = aa.fusion(tmp_path, tmp_path, NOW)
    f = b["last_fill"]
    assert f["source"] == "inferred:equity_step"
    assert f["ts_window"] == [_iso(t0 + timedelta(hours=1)), _iso(t0 + timedelta(hours=2))]
    assert f["side"] == "buy" and f["lots"] == 0.01
    assert b["balance"] == 612.5
    # a terminal moved to a 100k account is a switch, never a fill
    _jsonl(tmp_path / "web/equity_history.jsonl", [
        {"at": _iso(t0), "equity": 612.5}, {"at": _iso(t0 + timedelta(hours=1)),
                                            "equity": 99666.72}])
    _json(tmp_path / "data/account_state.json",
          {"updated_at": _iso(NOW), "server": "FTMO-Server2", "balance": 99666.72,
           "equity": 99666.72, "today_closed_pnl": 0.0})
    b = aa.fusion(tmp_path, tmp_path, NOW)
    assert b["last_fill"] is None
    assert b["balance"] is None and b["account_state_server"] == "FTMO-Server2"
    assert b["facts"] == "PARTIAL"
    assert any("not Fusion" in n for n in b["notes"])


# ------------------------------------------------------------------ the write

def test_the_write_is_atomic_and_whole(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "reports/ACCOUNT_ACTIVITY.json"
    aa.write({"v": 1}, out)
    assert json.loads(out.read_text("utf-8")) == {"v": 1}
    seen: list[tuple[str, str]] = []
    real = os.replace

    def spy(src: Any, dst: Any) -> None:
        seen.append((Path(src).name, Path(dst).name))
        assert json.loads(Path(src).read_text("utf-8")) == {"v": 2}  # whole before the swap
        assert json.loads(Path(dst).read_text("utf-8")) == {"v": 1}  # old one still readable
        real(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    aa.write({"v": 2}, out)
    assert seen and seen[0][1] == "ACCOUNT_ACTIVITY.json" and seen[0][0].endswith(".tmp")
    assert json.loads(out.read_text("utf-8")) == {"v": 2}
    assert sorted(p.name for p in out.parent.iterdir()) == ["ACCOUNT_ACTIVITY.json"]

    def boom(src: Any, dst: Any) -> None:
        raise OSError("disk")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        aa.write({"v": 3}, out)
    assert json.loads(out.read_text("utf-8")) == {"v": 2}  # the old report survives
    assert sorted(p.name for p in out.parent.iterdir()) == ["ACCOUNT_ACTIVITY.json"]


def test_main_writes_only_its_own_report(tmp_path: Path) -> None:
    _ftmo_desk(tmp_path)
    before = {p for p in tmp_path.rglob("*") if p.is_file()}
    assert aa.main(["--desk", str(tmp_path), "--repo", str(tmp_path)]) == 0
    after = {p for p in tmp_path.rglob("*") if p.is_file()}
    assert after - before == {tmp_path / "reports/ACCOUNT_ACTIVITY.json"}
    doc = json.loads((tmp_path / "reports/ACCOUNT_ACTIVITY.json").read_text("utf-8"))
    assert doc["schema"] == aa.SCHEMA and set(doc["accounts"]) == {"fusion", "e8", "ftmo"}


def test_imports_only_the_standard_library() -> None:
    tree = ast.parse(Path(aa.__file__).read_text("utf-8"))
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
    assert mods <= set(sys.stdlib_module_names) | {"__future__"}, mods


def test_the_hourly_cycle_runs_it_on_the_core_plan() -> None:
    cycle = (DESK / "research/hourly_cycle.py").read_text("utf-8")
    assert '_costed("account_activity"' in cycle
    assert '"research/account_activity.py"' in cycle
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["account_activity"] == "meta"
