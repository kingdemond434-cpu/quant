"""Trader-brain rows #2, #6, #7 (2026-11-13): the event window, the spread state and the journal.

Each test pins one decision the code makes on the money path or feeds to it:
  * an event defers only the symbols whose currencies it reprices;
  * a sleeve whose replayed trades LOSE inside the window is DEFER, one that EARNS there is
    TRADE_THROUGH, and too few paired days is NO_EVIDENCE (Holm across sleeves);
  * the spread threshold k is the smallest multiple the desk's own fill costs support, or null;
  * the gateway's entry deferral defers, journals and bills -- and an absent report defers
    nothing;
  * the journal row's exit kind, excursion and sticky regime.
"""
from __future__ import annotations

import ast
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.execution import event_guard as eg  # noqa: E402
from research import event_window_policy as ewp  # noqa: E402
from research import spread_state as ss  # noqa: E402
from research import trade_journal as tj  # noqa: E402

FOMC = datetime(2026, 12, 9, 19, 0, tzinfo=UTC)


def _calendar(tmp_path: Path, when: datetime = FOMC, name: str = "FOMC decision") -> Path:
    p = tmp_path / "event_calendar.json"
    p.write_text(json.dumps({"valid_through": "2027-12-31", "source": "test",
                             "events": [{"utc": when.isoformat(), "name": name,
                                         "impact": "high"}]}), "utf-8")
    return p


# ------------------------------------------------------------------ #2: which symbols an event hits

def test_an_fomc_window_defers_usd_symbols_and_not_a_cross_without_usd(tmp_path):
    cal = _calendar(tmp_path)
    at = FOMC - timedelta(minutes=10)
    assert eg.check_symbol("EURUSD", at, calendar=cal).state == "BLACKOUT"
    assert eg.check_symbol("XAUUSD", at, calendar=cal).state == "BLACKOUT"
    assert eg.check_symbol("EURCHF", at, calendar=cal).state == "CLEAR"


def test_outside_the_window_nothing_is_deferred(tmp_path):
    cal = _calendar(tmp_path)
    assert eg.check_symbol("EURUSD", FOMC + timedelta(hours=3), calendar=cal,
                           before_min=30, after_min=60).state == "CLEAR"


def _info(r_in: float, r_out: float, days: int) -> dict:
    trades = []
    events = []
    for i in range(days):
        ev = FOMC + timedelta(days=i)
        events.append({"utc": ev.isoformat(), "name": "FOMC decision", "_when": ev})
        trades.append((ev + timedelta(minutes=5), r_in + 0.01 * (i % 3)))
        trades.append((ev - timedelta(hours=6), r_out))
    return {"info": {"symbol": "EURUSD", "source": "shadow", "f": 0.01, "trades": trades},
            "events": events}


@pytest.mark.parametrize(("r_in", "verdict"), [(-1.0, "DEFER"), (1.5, "TRADE_THROUGH")])
def test_the_sleeves_own_window_trades_decide(r_in, verdict):
    case = _info(r_in, 0.2, days=8)
    rows = {"s": ewp.judge(case["info"], case["events"])}
    ewp.holm(rows)
    assert rows["s"]["paired_days"] == 8
    assert rows["s"]["verdict"] == verdict


def test_too_few_paired_days_is_no_evidence():
    case = _info(-1.0, 0.2, days=ewp.MIN_DAYS - 1)
    rows = {"s": ewp.judge(case["info"], case["events"])}
    ewp.holm(rows)
    assert rows["s"]["verdict"] == "NO_EVIDENCE"


# ------------------------------------------------------------------ #6: k from the desk's fills

def test_k_is_the_smallest_multiple_whose_wide_fills_cost_twice_the_normal():
    obs = ([{"ratio": 1.0, "cost_r": 0.02}] * 40 + [{"ratio": 1.8, "cost_r": 0.02}] * 12
           + [{"ratio": 3.5, "cost_r": 0.05}] * 12)
    k, ladder = ss.choose_k(obs)
    assert k == 2.0
    assert [r["qualifies"] for r in ladder][:2] == [False, True]


def test_no_supporting_evidence_leaves_the_gate_off():
    k, _ = ss.choose_k([{"ratio": 4.0, "cost_r": 0.02}] * 5 + [{"ratio": 1.0, "cost_r": 0.02}] * 50)
    assert k is None


# ------------------------------------------------------------------ the gateway's deferral

_GW = (_DESK / "mt5desk" / "gateway.py").read_text("utf-8")
_TREE = ast.parse(_GW)


def _gateway(ns: dict) -> dict:
    keep = [n for n in _TREE.body if isinstance(n, ast.FunctionDef)
            and n.name in ("_report", "event_deferral", "spread_deferral", "entry_deferral")]
    seed = {"json": json, "datetime": datetime, "UTC": UTC, "Path": Path, "pd": pd,
            "_REPORT_CACHE": {}, "_CAL_WARNED": {}, **ns}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(_DESK / "mt5desk" / "gateway.py"),
                 "exec"), seed)
    return seed


def _env(tmp_path: Path, *, policy: dict | None, spread: dict | None, cal: Path,
         ask: float = 1.10020, bid: float = 1.10000, hour: int = 22) -> tuple[dict, list, list]:
    logs: list[str] = []
    refused: list[tuple] = []
    until = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    pol, spr = tmp_path / "EVENT_WINDOW_POLICY.json", tmp_path / "SPREAD_STATE.json"
    if policy is not None:
        pol.write_text(json.dumps({"valid_until": until, **policy}), "utf-8")
    if spread is not None:
        spr.write_text(json.dumps({"valid_until": until, **spread}), "utf-8")
    t = int(pd.Timestamp(f"2026-11-13 {hour:02d}:00", tz="UTC").timestamp())
    mt5 = SimpleNamespace(symbol_info=lambda s: SimpleNamespace(point=0.00001),
                          symbol_info_tick=lambda s: SimpleNamespace(ask=ask, bid=bid, time=t))
    ns = _gateway({"EVENT_POLICY": pol, "SPREAD_STATE": spr, "EVENT_CALENDAR": cal,
                   "log": logs.append, "mt5": mt5,
                   "journal_refusal": lambda *a, **k: refused.append(a)})
    return ns, logs, refused


def test_no_reports_and_no_event_defer_nothing(tmp_path):
    ns, _, refused = _env(tmp_path, policy=None, spread=None,
                          cal=_calendar(tmp_path, datetime.now(UTC) + timedelta(days=3)))
    assert ns["entry_deferral"]({}, "s", "EURUSD") is None
    assert refused == []


def test_a_live_window_defers_unless_the_sleeve_trades_through(tmp_path):
    cal = _calendar(tmp_path, datetime.now(UTC) + timedelta(minutes=10))
    win = {"window": {"before_min": 30, "after_min": 60}}
    ns, _, refused = _env(tmp_path, policy={**win, "policy": {}}, spread=None, cal=cal)
    why = ns["entry_deferral"]({}, "s", "EURUSD")
    assert why and "NO_EVIDENCE" in why
    assert refused and refused[0][3] == "event_defer"
    ns, _, refused = _env(tmp_path, policy={**win, "policy": {"s": {"verdict": "TRADE_THROUGH"}}},
                          spread=None, cal=cal)
    assert ns["entry_deferral"]({}, "s", "EURUSD") is None
    assert refused == []


def test_a_spread_past_k_times_the_hour_median_defers(tmp_path):
    cal = _calendar(tmp_path, datetime.now(UTC) + timedelta(days=3))
    doc = {"k": 3.0, "hour_p50_pts": {"EURUSD": {"22": 5.0}}}
    ns, _, refused = _env(tmp_path, policy=None, spread=doc, cal=cal)     # 20 pts > 15
    assert "spread 20.0 pts" in (ns["entry_deferral"]({}, "s", "EURUSD") or "")
    assert refused[0][3] == "spread_defer"
    ns, _, _ = _env(tmp_path, policy=None, spread=doc, cal=cal, ask=1.10010)   # 10 pts
    assert ns["entry_deferral"]({}, "s", "EURUSD") is None
    ns, _, _ = _env(tmp_path, policy=None, spread={**doc, "k": None}, cal=cal)
    assert ns["entry_deferral"]({}, "s", "EURUSD") is None


def test_an_expired_report_is_no_report(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"k": 2.0, "valid_until": "2020-01-01T00:00:00+00:00"}), "utf-8")
    ns = _gateway({})
    assert ns["_report"](p) == {}


# ------------------------------------------------------------------ #7: the journal row

def _led(**kw) -> dict:
    return {"deal": 1, "symbol": "XAUUSD", "sleeve": "gold_asia", "entry_side": 0,
            "entry_price": 100.0, "sl": 90.0, "tp": 120.0, "fill_price": 110.0,
            "entry_time": "2026-09-01T10:00:00+00:00", "exit_time": "2026-09-01T10:03:00+00:00",
            "r_multiple": 1.0, **kw}


@pytest.mark.parametrize(("fill", "stamp", "kind", "basis"), [
    (90.4, None, "sl", "inferred"), (119.5, None, "tp", "inferred"),
    (105.0, None, "desk", "inferred"), (105.0, "stop_out", "stop_out", "gateway")])
def test_exit_kind(fill, stamp, kind, basis):
    row = _led(fill_price=fill, **({"exit_kind": stamp} if stamp else {}))
    assert tj.exit_kind(row) == (kind, basis)


def test_excursion_reads_the_finest_bars_in_risk_units(tmp_path, monkeypatch):
    idx = pd.date_range("2026-09-01 09:58", periods=8, freq="1min", tz="UTC")
    pd.DataFrame({"high": [101, 101, 104, 106, 103, 102, 130, 130],
                  "low": [99, 99, 97, 98, 100, 101, 80, 80]}, index=idx) \
        .to_parquet(tmp_path / "XAUUSD_M1.parquet")
    monkeypatch.setattr(tj, "UNIVERSE", tmp_path)
    ex = tj.excursion(_led())
    assert ex["excursion_tf"] == "M1"
    assert ex["mfe_r"] == pytest.approx(0.6)          # high 106 over a 10-point risk
    assert ex["mae_r"] == pytest.approx(0.3)          # low 97
    monkeypatch.setattr(tj, "UNIVERSE", tmp_path / "none")
    assert tj.excursion(_led())["mfe_r"] is None


def test_a_regime_read_at_the_time_survives_a_later_rebuild():
    prior = {"regime": "trend_up", "mfe_r": 0.6, "mae_r": 0.3, "excursion_tf": "M1",
             "excursion_why": None}
    fresh = {"regime": tj.UNLABELLED, "mfe_r": None, "mae_r": None, "excursion_tf": None,
             "excursion_why": "no bars"}
    out = tj.merge(prior, fresh)
    assert out["regime"] == "trend_up" and out["mfe_r"] == 0.6


def test_the_journal_row_carries_no_money(tmp_path):
    row = tj.journal_row(_led(pl_quote=123.4, account_key="sha256:x", server="srv"), None, None,
                         {}, {}, [])
    assert not {"pl_quote", "account_key", "server"} & set(row)
    assert row["r"] == 1.0 and row["exit_kind"] == "desk"


# ------------------------------------------------------------------ the calendar's path and gaps

def test_the_calendar_path_does_not_depend_on_the_working_directory(monkeypatch):
    monkeypatch.chdir(_DESK)
    assert eg.CALENDAR.is_absolute()
    assert eg.CALENDAR == _ROOT / "data" / "event_calendar.json"


def test_a_missing_calendar_defers_nothing_and_says_so_once(tmp_path):
    ns, logs, refused = _env(tmp_path, policy=None, spread=None, cal=tmp_path / "absent.json")
    for _ in range(3):
        assert ns["entry_deferral"]({}, "s", "EURUSD") is None
    assert refused == []
    assert sum("EVENT CALENDAR" in m for m in logs) == 1


@pytest.mark.parametrize(("cal", "state"), [
    ({"state": "UNREADABLE", "why": "FileNotFoundError"}, "RED"),
    ({"state": "READ", "n_events": 3, "valid_through": ""}, "RED"),
    ({"state": "READ", "n_events": 3, "valid_through": "2020-01-01"}, "RED"),
    ({"state": "READ", "n_events": 3, "valid_through": "2099-01-01"}, "GREEN")])
def test_the_policy_leg_turns_red_when_the_event_gate_is_off(cal, state):
    assert ewp.calendar_health(cal, datetime.now(UTC))["state"] == state
