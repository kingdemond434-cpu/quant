"""The scalp lane reaches capital: automatic promotion and a replay-faithful executor.

Principal 2026-09-04: "all promotion candidates get into the live account immediately, no
waiting, no permission, fully automatically, always." Before this, `scalp_shadow.py` could mature
a sleeve to PROMOTION_CANDIDATE and nothing read that status -- a candidate that could never
reach capital, the exact gap the growth rules forbid.

What is pinned:

  * a matured, certified, Fusion-fed scalp candidate is written LIVE with its exact recipe on the
    promoter's next run, idempotently; an uncertified one is BLOCKED_UNIVERSAL_GATES; a
    proxy-fed clock carries no capital authority;
  * retirement kills the row in the scalp lane itself, so it is never re-promoted;
  * the planner computes the anti-breakout short with the replay's geometry, refuses when there
    is no signal, adds slices only on the replay's conditions, and quarters lots honestly;
  * the gateway's scalp executor exists, is called after the family executor, sizes through
    `promoted_lot` with the book's fraction, logs instead of trading when unarmed, places the
    first slice with the plan's stop and target when armed, never double-fires on one bar, and
    time-exits only its own sleeve's positions.
"""
from __future__ import annotations

import ast
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import promoter  # noqa: E402
from mt5desk import provenance  # noqa: E402
from mt5desk import scalp_exec as sx  # noqa: E402

_ACC = {"login": 5551234, "server": "FusionMarkets-Live", "kind": provenance.LIVE}
_NAME = "xau_m15_anti_breakout"
_CAND = {"status": "PROMOTION_CANDIDATE", "timeframe": "M15",
         "choice": {"family": "anti_donchian_breakout", "session": "all", "stop_atr": 1.0,
                    "target_atr": 1.5, "max_hold": 6},
         "n": 65, "days": 0, "expectancy_r": 0.068, "max_drawdown_r": -6.0,
         "promotion_authority": True}


@pytest.fixture
def desk(tmp_path, monkeypatch):
    shadow_dir = tmp_path / "reports" / "shadow"
    shadow_dir.mkdir(parents=True)
    (tmp_path / "data").mkdir()
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(promoter, "SHADOW_DIR", shadow_dir)
    monkeypatch.setattr(promoter, "SLEEVES_FILE", tmp_path / "data" / "sleeves.json")
    monkeypatch.setattr(promoter, "LEDGER", tmp_path / "data" / "live_ledger.jsonl")
    monkeypatch.setattr(promoter, "LOG", tmp_path / "logs" / "promoter.log")
    monkeypatch.setattr(promoter, "GOLD_RETIRED_FILE", tmp_path / "data" / "GOLD_RETIRED.json")
    monkeypatch.setattr(promoter.provenance, "current_account", lambda _acc: _ACC)
    authority: set = set()
    monkeypatch.setattr(promoter, "authorized_specs", lambda base=None: set(authority))

    class Desk:
        def certify(self, *names: str) -> None:
            for n in names:
                authority.add(("XAUUSD", n, None, "gold_scalp", False))

        def scalp(self, rows: dict) -> None:
            (shadow_dir / "scalp_shadow_state.json").write_text(
                json.dumps({"sleeves": rows}), encoding="utf-8")

        def read_scalp(self) -> dict:
            return json.loads((shadow_dir / "scalp_shadow_state.json").read_text("utf-8"))

        def ledger(self, rows: list[dict]) -> None:
            (tmp_path / "data" / "live_ledger.jsonl").write_text(
                "\n".join(json.dumps({**provenance.stamp(_ACC), **r}) for r in rows), "utf-8")

        def sleeves(self) -> list[dict]:
            p = tmp_path / "data" / "sleeves.json"
            return json.loads(p.read_text("utf-8"))["sleeves"] if p.exists() else []

    return Desk()


# ------------------------------------------------------------------------------- the promoter
def test_a_matured_certified_scalp_candidate_goes_live_immediately_and_idempotently(desk):
    desk.certify(_NAME)
    desk.scalp({_NAME: dict(_CAND)})
    promoter.main()
    (s,) = desk.sleeves()
    assert s["status"] == "LIVE" and s["exec"] == "scalp_market" and s["symbol"] == "XAUUSD"
    assert (s["timeframe"], s["family"], s["session"]) == ("M15", "anti_donchian_breakout", "all")
    assert (s["stop_atr"], s["target_atr"], s["max_hold"]) == (1.0, 1.5, 6)
    assert s["risk_frac"] == promoter.PROMOTED_RISK_FRAC and s["lot"] == "auto_ramp"
    promoter.main()
    assert len(desk.sleeves()) == 1


def test_an_uncertified_scalp_candidate_is_blocked_not_promoted(desk):
    desk.scalp({_NAME: dict(_CAND)})
    promoter.main()
    assert desk.sleeves() == []
    assert desk.read_scalp()["sleeves"][_NAME]["status"] == "BLOCKED_UNIVERSAL_GATES"


def test_a_proxy_fed_scalp_clock_carries_no_capital_authority(desk):
    desk.certify(_NAME)
    desk.scalp({_NAME: {**_CAND, "promotion_authority": False}})
    promoter.main()
    assert desk.sleeves() == []
    assert desk.read_scalp()["sleeves"][_NAME]["status"] == "PROMOTION_CANDIDATE"


def test_a_retired_scalp_sleeve_is_killed_in_its_own_lane_and_never_re_promoted(desk):
    desk.certify(_NAME)
    desk.scalp({_NAME: dict(_CAND)})
    promoter.main()
    assert desk.sleeves()[0]["status"] == "LIVE"
    rng = np.random.default_rng(1)
    desk.ledger([{"sleeve": _NAME, "r_multiple": float(-abs(rng.normal(0.4, 0.2)))}
                 for _ in range(12)])
    promoter.main()
    (s,) = desk.sleeves()
    assert s["status"] == "RETIRED" and "roll20" in s["retire_reason"]
    assert desk.read_scalp()["sleeves"][_NAME]["status"] == "KILL"
    promoter.main()
    assert [x["status"] for x in desk.sleeves()] == ["RETIRED"]


# ------------------------------------------------------------------------------- the planner
def _bars(n: int = 200, breakout: bool = True, seed: int = 0, recent: bool = False,
          ) -> pd.DataFrame:
    """M15 bars: a quiet range, then a last closed bar that closes above the 20-bar high.

    `recent` ends the frame at the current quarter-hour, so an executor test's time exit lies
    in the future rather than firing on bars dated last week.
    """
    rng = np.random.default_rng(seed)
    if recent:
        end = pd.Timestamp.now(tz="UTC").floor("15min") - pd.Timedelta(minutes=15)
        idx = pd.date_range(end=end, periods=n, freq="15min", tz="UTC")
    else:
        idx = pd.date_range("2026-09-01 08:00", periods=n, freq="15min", tz="UTC")
    close = 2000.0 + np.cumsum(rng.normal(0, 0.3, n))
    close = np.clip(close, 1997.0, 2003.0)
    high, low = close + 0.6, close - 0.6
    opn = np.r_[close[0], close[:-1]]
    if breakout:
        close[-1], high[-1] = 2012.0, 2012.5
    return pd.DataFrame({"open": opn, "high": high, "low": low, "close": close,
                         "tick_volume": rng.integers(50, 200, n).astype(float)}, index=idx)


def test_plan_entry_is_the_anti_breakout_short_with_the_replays_geometry() -> None:
    closed = _bars()
    plan = sx.plan_entry(closed, tf="M15", family="anti_donchian_breakout", session="all",
                         stop_atr=1.0, target_atr=1.5, max_hold=6, bid=2011.8, ask=2012.1)
    assert plan is not None and plan.side == -1
    assert plan.entry_ref == 2011.8                                  # a short fills at the bid
    atr = sx.last_closed_atr(closed)
    assert plan.atr == pytest.approx(atr) and atr > 0
    assert plan.stop == pytest.approx(2011.8 + 1.0 * atr)
    assert plan.target == pytest.approx(2011.8 - 1.5 * atr)
    assert plan.stop_dist == pytest.approx(atr)
    forming = closed.index[-1] + pd.Timedelta(minutes=15)
    assert plan.bar_time == forming.isoformat()
    assert plan.ttl_until == (forming + pd.Timedelta(minutes=15 * 7)).isoformat()


def test_no_signal_means_no_plan_and_an_unknown_family_is_refused() -> None:
    quiet = _bars(breakout=False)
    assert sx.plan_entry(quiet, tf="M15", family="anti_donchian_breakout", session="all",
                         stop_atr=1.0, target_atr=1.5, max_hold=6, bid=2000.0, ask=2000.3) is None
    with pytest.raises(KeyError):
        sx.plan_entry(_bars(), tf="M15", family="not_a_family", session="all", stop_atr=1.0,
                      target_atr=1.5, max_hold=6, bid=2011.8, ask=2012.1)


def test_add_on_slices_follow_the_replays_three_conditions() -> None:
    closed = _bars()
    kw = {"tf": "M15", "family": "anti_donchian_breakout", "session": "all", "side": -1}
    assert sx.addon_allowed(closed, **kw, stop=2015.0, depth=1, price=2011.0)
    assert not sx.addon_allowed(closed, **kw, stop=2015.0, depth=4, price=2011.0)
    assert not sx.addon_allowed(closed, **kw, stop=2015.0, depth=1, price=2016.0)
    assert not sx.addon_allowed(_bars(breakout=False), **kw, stop=2015.0, depth=1, price=2000.0)


def test_basket_target_and_lot_quartering() -> None:
    assert sx.basket_target([(100.0, 1.0), (102.0, 1.0)], -1, 1.5, 2.0) == pytest.approx(98.0)
    assert sx.slice_lot(0.12, 0.01, 0.01) == (0.03, "bounded_structural")
    assert sx.slice_lot(0.03, 0.01, 0.01) == (0.03, "single")
    assert sx.slice_lot(0.005, 0.01, 0.01) == (0.0, "too_small")


def test_frame_from_rates_reads_broker_rows() -> None:
    rows = [{"time": 1_756_710_000 + 900 * i, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5,
             "tick_volume": 3} for i in range(3)]
    df = sx.frame_from_rates(rows)
    assert df.index.tz is not None and list(df.columns[:4]) == ["open", "high", "low", "close"]
    assert len(df) == 3 and df["tick_volume"].iloc[0] == 3


# ------------------------------------------------------------------------------- the gateway
_GW_SRC = (_DESK / "mt5desk" / "gateway.py").read_text("utf-8")
_GW_TREE = ast.parse(_GW_SRC)


def _exec(names: tuple[str, ...], ns: dict) -> dict:
    keep = [n for n in _GW_TREE.body if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=keep, type_ignores=[]), "<gw>", "exec"), ns)
    return ns


def test_the_gateway_wires_the_scalp_executor_into_the_money_path() -> None:
    names = {n.name for n in _GW_TREE.body if isinstance(n, ast.FunctionDef)}
    assert {"run_scalp_sleeves", "close_sleeve_positions", "_retarget_sleeve_positions",
            "_sleeve_positions"} <= names
    main_src = next(ast.get_source_segment(_GW_SRC, n) for n in _GW_TREE.body
                    if isinstance(n, ast.FunctionDef) and n.name == "main")
    assert main_src.index("run_family_sleeves(st, sleeves, equity)") < \
        main_src.index("run_scalp_sleeves(st, sleeves, equity)")
    sleeve_set_src = next(ast.get_source_segment(_GW_SRC, n) for n in _GW_TREE.body
                          if isinstance(n, ast.FunctionDef) and n.name == "sleeve_set")
    assert '"scalp_market"' in sleeve_set_src and '"stop_atr"' in sleeve_set_src
    assert main_src.count('("family_market", "scalp_market")') >= 2
    assert _GW_SRC.count('from_book=(s.get("sized_by") == "allocator_book")') >= 3


def _fake_mt5(bars: pd.DataFrame, *, positions: list | None = None) -> SimpleNamespace:
    sent: list[dict] = []
    rows = [{"time": int(ts.timestamp()), "open": r.open, "high": r.high, "low": r.low,
             "close": r.close, "tick_volume": r.tick_volume}
            for ts, r in bars.iterrows()]
    m = SimpleNamespace(
        TIMEFRAME_M15=15, TRADE_ACTION_DEAL=1, TRADE_ACTION_SLTP=6, ORDER_TYPE_BUY=0,
        ORDER_TYPE_SELL=1, POSITION_TYPE_BUY=0, sent=sent,
        copy_rates_from_pos=lambda symbol, tf, start, count: rows,
        symbol_info_tick=lambda symbol: SimpleNamespace(bid=2011.8, ask=2012.1),
        symbol_info=lambda symbol: SimpleNamespace(volume_min=0.01, volume_step=0.01),
        positions_get=lambda symbol=None: list(positions or []),
        order_send=lambda req: (sent.append(req) or SimpleNamespace(retcode=10009, order=7,
                                                                    comment="done")),
    )
    return m


def _ns(tmp_path: Path, mt5: SimpleNamespace, *, armed_file: bool) -> dict:
    logs: list[str] = []
    intents: list[dict] = []
    enable = tmp_path / "GENERIC_EXEC_ENABLED"
    if armed_file:
        enable.write_text("", "utf-8")
    ns = {"mt5": mt5, "log": logs.append, "MAGIC": 1, "GENERIC_EXEC_ENABLED": enable,
          "datetime": datetime, "UTC": UTC, "pd": pd,
          "promoted_lot": lambda *a, **k: 0.12, "sleeve_live_n": lambda name: 0,
          "margin_ok": lambda *a, **k: True, "_record_intent": lambda **row: intents.append(row),
          "_policy_advice": lambda *a, **k: {"policy": "MARKET"}, "diagnose": lambda *a: "",
          "_logs": logs, "_intents": intents}
    return _exec(("run_scalp_sleeves", "close_sleeve_positions", "_retarget_sleeve_positions",
                  "_sleeve_positions"), ns)


def _sleeve() -> dict:
    return {"name": _NAME, "symbol": "XAUUSD", "exec": "scalp_market", "timeframe": "M15",
            "family": "anti_donchian_breakout", "session": "all", "stop_atr": 1.0,
            "target_atr": 1.5, "max_hold": 6, "risk_frac": 0.03, "lot": "auto_ramp"}


def _with_forming(bars: pd.DataFrame) -> pd.DataFrame:
    """The broker hands back the forming bar too; the executor must drop it itself."""
    forming = bars.index[-1] + pd.Timedelta(minutes=15)
    row = pd.DataFrame({"open": [2012.0], "high": [2012.2], "low": [2011.5], "close": [2011.9],
                        "tick_volume": [10.0]}, index=pd.DatetimeIndex([forming]))
    return pd.concat([bars, row])


def test_unarmed_the_scalp_executor_logs_the_order_and_places_nothing(tmp_path) -> None:
    mt5 = _fake_mt5(_with_forming(_bars(recent=True)))
    ns = _ns(tmp_path, mt5, armed_file=False)
    st = {"armed": True}
    ns["run_scalp_sleeves"](st, [_sleeve()], 10_000.0)
    assert mt5.sent == [] and any("WOULD PLACE" in x for x in ns["_logs"])
    assert "basket" not in st["scalp"][_NAME]


def test_armed_the_first_slice_is_placed_with_the_plans_levels_once_per_bar(tmp_path) -> None:
    bars = _with_forming(_bars(recent=True))
    mt5 = _fake_mt5(bars)
    ns = _ns(tmp_path, mt5, armed_file=True)
    st = {"armed": True}
    ns["run_scalp_sleeves"](st, [_sleeve()], 10_000.0)
    (req,) = mt5.sent
    plan = sx.plan_entry(bars.iloc[:-1], tf="M15", family="anti_donchian_breakout",
                         session="all", stop_atr=1.0, target_atr=1.5, max_hold=6,
                         bid=2011.8, ask=2012.1, forming_time=bars.index[-1])
    assert req["type"] == mt5.ORDER_TYPE_SELL and req["volume"] == pytest.approx(0.03)
    assert req["sl"] == pytest.approx(plan.stop) and req["tp"] == pytest.approx(plan.target)
    assert req["comment"] == f"DW{_NAME}"
    (intent,) = ns["_intents"]
    assert intent["sleeve"] == _NAME and intent["slice_depth"] == 1
    basket = st["scalp"][_NAME]["basket"]
    assert basket["side"] == -1 and basket["mode"] == "bounded_structural"
    assert st["scalp"][_NAME]["open_ttl_until"] == plan.ttl_until
    # The same bar again: nothing new is placed.
    mt5.positions_get = lambda symbol=None: [SimpleNamespace(comment=f"DW{_NAME}", ticket=7,
                                                             volume=0.03, type=1)]
    ns["run_scalp_sleeves"](st, [_sleeve()], 10_000.0)
    assert len(mt5.sent) == 1


def test_the_time_exit_closes_only_this_sleeves_positions(tmp_path) -> None:
    # Quiet bars: after the time exit no new signal fires at this bar's open, so the basket must
    # be gone. (With a signal, re-entering at the bar after the exit is the replay's own rule.)
    bars = _with_forming(_bars(breakout=False, recent=True))
    mine = SimpleNamespace(comment=f"DW{_NAME}", ticket=7, volume=0.03, type=1)
    other = SimpleNamespace(comment="DWgold_asia", ticket=8, volume=0.10, type=0)
    mt5 = _fake_mt5(bars, positions=[mine, other])
    ns = _ns(tmp_path, mt5, armed_file=True)
    past = (datetime.now(tz=UTC) - timedelta(minutes=1)).isoformat()
    st = {"armed": True, "scalp": {_NAME: {"open_ttl_until": past, "last_signal_bar": "x",
                                           "basket": {"side": -1, "stop": 2015.0,
                                                      "target": 2005.0, "atr": 1.0,
                                                      "target_atr": 1.5,
                                                      "mode": "bounded_structural",
                                                      "entries": [[2011.8, 0.03]]}}}}
    ns["run_scalp_sleeves"](st, [_sleeve()], 10_000.0)
    closes = [r for r in mt5.sent if "position" in r]
    assert [r["position"] for r in closes] == [7]
    assert "basket" not in st["scalp"][_NAME] and "open_ttl_until" not in st["scalp"][_NAME]
