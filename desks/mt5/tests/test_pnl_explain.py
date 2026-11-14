"""`pnl_explain` (finding K4): every account's realised P&L split, per day, into signal, entry
slippage, commission, swap, fees and FX conversion -- and the identity holds to the cent.

  0. a same-currency trade: the components sum to the booked net, slippage has the right sign;
  1. a cross-currency trade: FX conversion is the broker's own exit rate against the entry rate;
     the traded pair supplies its own rate; another pair's bars supply it otherwise;
  2. no intent -> slippage UNMEASURED and the edge reported unsplit (never a zero slip);
  3. accounts are never pooled; the account currency is read or inferred from the broker's own
     conversion; a trade that does not reconcile is listed with its residual;
  4. closed days are appended once, today never; the leg and graph are wired;
  5. a cross-currency trade's FX is labelled IMPLIED and its residual UNTESTED (never a clean
     check); an undated trade is counted unexplainable, never dated 1970;
  6. the publishable view and stdout carry ratios and counts only: no amount, server or key.
All inputs are synthetic.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import pnl_explain as P  # noqa: E402

META = {"XAUUSD": {"currency_profit": "USD", "contract_size": 100.0},
        "EURCHF": {"currency_profit": "CHF", "contract_size": 100000.0},
        "AUDUSD": {"currency_profit": "USD", "contract_size": 100000.0},
        "EURUSD": {"currency_profit": "USD", "contract_size": 100000.0}}
NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
ACC_A = {"account_key": "sha256:aaaa1111", "server": "Demo-1", "account_kind": "live",
         "account_currency": "USD"}
ACC_B = {"account_key": "sha256:bbbb2222", "server": "Demo-2", "account_kind": "live"}


def _row(acc: dict, **kw) -> dict:
    base = {"time": "2026-11-12T15:00:00+00:00", "entry_time": "2026-11-12T08:00:00+00:00",
            "exit_time": "2026-11-12T15:00:00+00:00", "sleeve": "s1", "commission": 0.0,
            "swap": 0.0, "exit_fee": 0.0, "entry_cost_allocated": 0.0}
    return {**base, **acc, **kw}


def test_same_currency_identity_and_slippage_sign():
    # long gold, asked 2000.00, filled 2000.30 (paid 0.30), exited 2010.00, 0.10 lot
    # profit = (2010 - 2000.30) * 0.1 * 100 = 97.0 ; net = 97 - 0.7 comm - 0.3 swap = 96.0
    r = _row(ACC_A, deal=1, symbol="XAUUSD", entry_side=0, entry_price=2000.30,
             fill_price=2010.0, volume=0.1, sl=1990.0, tp=2030.0, commission=-0.7, swap=-0.3,
             pl_quote=96.0, entry_order=77)
    rep = P.explain(now=NOW, ledger=[r], prop=[], intents=[{"ticket": 77, "intended": 2000.0}],
                    meta=META, state={}, bars=None)
    (acc,) = rep["accounts"].values()
    t = acc["total"]
    assert acc["account_currency"] == "USD"
    assert t["signal"] == pytest.approx(100.0)
    assert t["entry_slippage"] == pytest.approx(-3.0)
    assert t["commission"] == pytest.approx(-0.7) and t["swap"] == pytest.approx(-0.3)
    assert t["fx_conversion"] == pytest.approx(0.0)
    assert t["residual"] == pytest.approx(0.0, abs=1e-9)
    assert t["coverage_slippage"] == 1.0
    assert t["n_residual_tested"] == 1 and t["coverage_residual_test"] == 1.0
    assert rep["latest_trades"][-1]["residual_status"] == P.MEASURED
    assert acc["daily"]["2026-11-12"]["net"] == pytest.approx(96.0)


def test_cross_currency_fx_from_the_traded_pair_and_from_bars():
    # EUR account, short EURCHF 0.10 at 0.9400 (asked 0.9402), exit 0.9300.
    # quote_gross = (0.93 - 0.94) * -1 * 0.1 * 1e5 = 100 CHF; broker books at 1/0.93
    prof = 100.0 / 0.93
    r = _row(ACC_B, deal=2, symbol="EURCHF", entry_side=1, entry_price=0.9400,
             fill_price=0.9300, volume=0.1, sl=0.95, tp=0.92, pl_quote=prof,
             account_currency="EUR", intended_entry=0.9402)
    rep = P.explain(now=NOW, ledger=[r], prop=[], intents=[], meta=META, state={}, bars=None)
    t = next(iter(rep["accounts"].values()))["total"]
    rate_e = 1 / 0.94
    assert t["fx_conversion"] == pytest.approx(100.0 * (1 / 0.93 - rate_e), abs=0.01)
    assert t["entry_slippage"] == pytest.approx(-(0.94 - 0.9402) * -1 * 1e4 * rate_e, abs=0.01)
    assert t["residual"] == pytest.approx(0.0, abs=0.01)
    assert t["coverage_fx"] == 1.0
    tr = rep["latest_trades"][-1]
    assert tr["fx_basis"] == P.IMPLIED and tr["residual_status"] == P.UNMEASURED
    assert t["n_residual_tested"] == 0 and t["coverage_residual_test"] == 0.0

    # EUR account trading gold (USD profit): the rate comes from EURUSD bars at entry
    idx = pd.date_range("2026-11-12 00:00", periods=24, freq="h", tz="UTC")
    eurusd = pd.DataFrame({"close": [1.10] * 12 + [1.12] * 12}, index=idx)
    r2 = _row(ACC_B, deal=3, symbol="XAUUSD", entry_side=0, entry_price=2000.0,
              fill_price=2010.0, volume=0.1, sl=1990.0, pl_quote=100.0 / 1.12,
              account_currency="EUR", intended_entry=2000.0)
    rep = P.explain(now=NOW, ledger=[r2], prop=[], intents=[], meta=META, state={},
                    bars=lambda s: eurusd if s == "EURUSD" else None)
    t = next(iter(rep["accounts"].values()))["total"]
    # entry 08:00 UTC -> the 1.10 close (bars before 12:00); exit at the broker's 1/1.12
    assert t["fx_conversion"] == pytest.approx(100.0 * (1 / 1.12 - 1 / 1.10), abs=0.01)
    assert t["signal"] == pytest.approx(100.0 / 1.10, abs=0.01)


def test_no_intent_is_unmeasured_never_a_zero_slip():
    r = _row(ACC_A, deal=4, symbol="XAUUSD", entry_side=0, entry_price=2000.0,
             fill_price=2005.0, volume=0.1, sl=1990.0, pl_quote=50.0)
    rep = P.explain(now=NOW, ledger=[r], prop=[], intents=[], meta=META, state={}, bars=None)
    t = next(iter(rep["accounts"].values()))["total"]
    assert t["entry_slippage"] == 0.0 and t["signal"] == 0.0
    assert t["signal_plus_slippage_unsplit"] == pytest.approx(50.0)
    assert t["coverage_slippage"] == 0.0
    tr = rep["latest_trades"][-1]
    assert tr["slippage_status"] == P.UNMEASURED and "slippage unmeasured" in " ".join(tr["why"])


def test_accounts_never_pooled_currency_inferred_and_unreconciled_listed():
    a = _row(ACC_A, deal=5, symbol="XAUUSD", entry_side=0, entry_price=2000.0,
             fill_price=2001.0, volume=0.1, sl=1990.0, pl_quote=10.0, intended_entry=2000.0)
    # account B is EUR and never says so: an EURUSD trade booked at ~1/price names EUR (the
    # pair's base currency) as the deposit currency
    b = _row(ACC_B, deal=6, symbol="EURUSD", entry_side=0, entry_price=1.1000,
             fill_price=1.1100, volume=0.1, sl=1.09, pl_quote=100.0 / 1.11,
             intended_entry=1.1000)
    bad = _row(ACC_A, deal=7, symbol="XAUUSD", entry_side=0, entry_price=2000.0,
               fill_price=2001.0, volume=0.1, sl=1990.0, pl_quote=9.0, intended_entry=2000.0)
    rep = P.explain(now=NOW, ledger=[a, b, bad], prop=[], intents=[], meta=META, state={},
                    bars=None)
    assert len(rep["accounts"]) == 2
    by_ccy = {v["account_currency"]: v for v in rep["accounts"].values()}
    assert set(by_ccy) == {"USD", "EUR"}
    assert "inferred" in by_ccy["EUR"]["account_currency_basis"]
    usd = by_ccy["USD"]
    assert usd["n_unreconciled"] == 1 and usd["unreconciled"][0]["deal"] == "7"
    assert usd["unreconciled"][0]["residual"] == pytest.approx(-1.0)


def test_closed_days_append_once_and_never_today(tmp_path):
    rows = [_row(ACC_A, deal=8, symbol="XAUUSD", entry_side=0, entry_price=2000.0,
                 fill_price=2001.0, volume=0.1, sl=1990.0, pl_quote=10.0,
                 intended_entry=2000.0),
            _row(ACC_A, deal=9, symbol="XAUUSD", entry_side=0, entry_price=2000.0,
                 fill_price=2002.0, volume=0.1, sl=1990.0, pl_quote=20.0, intended_entry=2000.0,
                 time="2026-11-13T09:00:00+00:00", exit_time="2026-11-13T09:00:00+00:00")]
    rep = P.explain(now=NOW, ledger=rows, prop=[], intents=[], meta=META, state={}, bars=None)
    path = tmp_path / "daily.jsonl"
    assert P.append_closed_days(rep, path, now=NOW) == 1
    assert P.append_closed_days(rep, path, now=NOW) == 0
    got = [json.loads(x) for x in path.read_text().splitlines()]
    assert [g["day"] for g in got] == ["2026-11-12"]


def test_empty_is_unmeasured():
    rep = P.explain(now=NOW, ledger=[], prop=[], intents=[], meta=META, state={}, bars=None)
    assert rep["status"] == P.UNMEASURED


def test_leg_and_graph_are_wired():
    hc = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"pnl_explain", "research/pnl_explain.py"' in hc and '"pnl_explain": pnx' in hc
    cg = (ROOT / "libs" / "ops" / "capability_graph.py").read_text("utf-8")
    assert '"desks/mt5/research/pnl_explain.py"' in cg
    from libs.research import layers
    assert layers.LEG_LAYER["pnl_explain"] == "execution"


def test_undated_trade_is_unexplainable_never_1970():
    r = _row(ACC_A, deal=10, symbol="XAUUSD", entry_side=0, entry_price=2000.0,
             fill_price=2001.0, volume=0.1, sl=1990.0, pl_quote=10.0, intended_entry=2000.0,
             time=None, exit_time=None)
    rep = P.explain(now=NOW, ledger=[r], prop=[], intents=[], meta=META, state={}, bars=None)
    (acc,) = rep["accounts"].values()
    t = acc["total"]
    assert t["n_trades"] == 1 and t["n_unexplainable"] == 1 and t["n_undated"] == 1
    assert acc["daily"] == {} and acc["n_unreconciled"] == 1
    assert "1970" not in json.dumps(rep)
    assert "undated" in " ".join(acc["unreconciled"][0]["why"])


def test_ratios_view_and_stdout_carry_no_amount_server_or_key(tmp_path, monkeypatch, capsys):
    rows = [_row(ACC_A, deal=11, symbol="XAUUSD", entry_side=0, entry_price=2000.30,
                 fill_price=2010.0, volume=0.1, sl=1990.0, commission=-0.7, swap=-0.3,
                 pl_quote=96.0, intended_entry=2000.0),
            _row(ACC_B, deal=12, symbol="EURUSD", entry_side=0, entry_price=1.1000,
                 fill_price=1.1100, volume=0.1, sl=1.09, pl_quote=100.0 / 1.11,
                 intended_entry=1.1000)]
    rep = P.explain(now=NOW, ledger=rows, prop=[], intents=[], meta=META, state={}, bars=None)
    v = P.ratios_view(rep)
    blob = json.dumps(v)
    for secret in ("Demo-1", "Demo-2", "aaaa1111", "bbbb2222", "96.0", "90.09"):
        assert secret not in blob
    assert set(v["accounts"]) == {"live#1", "live#2"}
    sh = v["accounts"]["live#1"]["total"]["shares"]
    assert sum(abs(x) for x in sh.values()) == pytest.approx(1.0, abs=1e-3)
    assert sh["signal"] > 0 > sh["entry_slippage"]

    monkeypatch.setattr(P, "explain", lambda **k: rep)
    monkeypatch.setattr(P, "REPORT", tmp_path / "r.json")
    monkeypatch.setattr(P, "RATIOS", tmp_path / "ratios.json")
    monkeypatch.setattr(P, "DAILY", tmp_path / "d.jsonl")
    assert P.main(["--no-write"]) == 0
    out = capsys.readouterr().out
    for secret in ("Demo-1", "Demo-2", "aaaa1111", "bbbb2222", "net=", "96.0"):
        assert secret not in out
    assert "cov_slip=" in out and "live#1" in out


def test_amount_bearing_outputs_are_gitignored():
    import subprocess
    for rel in ("desks/mt5/data/pnl_explain_daily.jsonl", "desks/mt5/reports/PNL_EXPLAIN.json"):
        rc = subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT).returncode
        assert rc == 0, f"{rel} carries account amounts and must stay on the box"
