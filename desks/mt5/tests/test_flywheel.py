"""The proprietary-data flywheel and the integration checks that keep it honest.

What is pinned:

  * the gateway writes every considered bracket -- taken or not -- to the decision ledger, and a
    veto that fires BEFORE the bracket exists (regime hibernate, the state gate) still records the
    two levels it refused, so the veto can be priced;
  * the counterfactual join replays a refused bracket as the pending stop it would have been:
    triggered brackets are priced, untriggered ones are NOT_TRIGGERED and never counted as zero;
  * the spread-state family reads the broker's spread from the ORIGINAL frame (the resampler drops
    it) and refuses to run on bars that carry no spread;
  * the alpha genome clusters two edges that would lose on the same day for the same reason;
  * a session phase is DEAD only when something was measured there and nothing pays;
    unmeasured is a different verdict and never a research target;
  * the capability graph refuses a producer nobody reads and an artifact that reaches no decision,
    and the desk's real graph passes it;
  * the point-in-time stamp never overwrites a producer's field, and an unstamped row is usable
    at no time;
  * the broker clock is recorded by the host that has a terminal and inherited by every other;
  * feedback engines own only their own rows in the deepening queue, and the queue works a gap
    the desk's own ledgers found before a crawler row.
"""
from __future__ import annotations

import ast
import importlib.util
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

from mt5desk.family_spread_state import family_spread_state  # noqa: E402

from libs.data import pit  # noqa: E402
from libs.ops import capability_graph as cg  # noqa: E402
from libs.regime.state_admission import Trade  # noqa: E402
from research import (  # noqa: E402  # noqa: E402
    alpha_genome,
    deepening_worker,
    regime_coverage,
    session_phase,
)
from research import counterfactual_markout as cfm
from research import opportunity_curve as oc

_GW_SRC = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
_GW_TREE = ast.parse(_GW_SRC)


# --------------------------------------------------------------------------- synthetic bars
def _bars(n: int = 2400, seed: int = 0, spread: bool = True) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-01-06", periods=n, freq="h", tz="UTC")
    close = 100.0 + np.cumsum(rng.normal(scale=0.1, size=n))
    high = close + rng.uniform(0.02, 0.15, n)
    low = close - rng.uniform(0.02, 0.15, n)
    open_ = np.r_[close[0], close[:-1]]
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                       "tick_volume": rng.integers(50, 500, n).astype(float)}, index=idx)
    df.index.name = "time"
    if spread:
        df["spread"] = rng.integers(10, 20, n).astype(float)
    return df


# --------------------------------------------------------------------------- spread state
def test_spread_state_refuses_bars_without_a_spread_column() -> None:
    assert family_spread_state(_bars(spread=False), mode="spike_reversion") == []


def test_spread_state_fades_a_move_made_on_a_spread_spike() -> None:
    """The move happened while the venue was charging ten times its norm to take the other
    side: liquidity, not information, and the family sells it."""
    df = _bars()
    spikes = list(range(900, 2300, 250))
    for i in spikes:
        df.iloc[i, df.columns.get_loc("spread")] = 400.0
        jump = 2.0
        df.iloc[i, df.columns.get_loc("close")] = df["close"].iloc[i - 1] + jump
        df.iloc[i, df.columns.get_loc("high")] = df["close"].iloc[i] + 0.05
    # hold_bars=1 so a noise-bar signal just before a spike cannot mask it with its cooldown.
    sig = family_spread_state(df, mode="spike_reversion", norm_window=240, hold_bars=1)
    assert sig, "a ten-ATR move on a top-percentile spread must fire"
    at_spike = [s for s in sig if s.time in {df.index[i] for i in spikes}]
    assert len(at_spike) == len(spikes), "every spike bar with a move must fire"
    for s in at_spike:
        assert s.side == -1                       # against an up-move
        assert s.stop > s.target                  # short geometry
        assert s.tag == "spread_state:spike_reversion"


def test_spread_state_does_not_fire_on_a_normal_spread() -> None:
    """The same jump on the instrument's TIGHTEST spread is information, and this family has no
    claim on it: none of the jump bars may fire, whatever the noise bars do."""
    df = _bars(seed=3)
    jumps = list(range(900, 2300, 250))
    for i in jumps:
        df.iloc[i, df.columns.get_loc("spread")] = 10.0          # the floor of its own range
        df.iloc[i, df.columns.get_loc("close")] = df["close"].iloc[i - 1] + 2.0
        df.iloc[i, df.columns.get_loc("high")] = df["close"].iloc[i] + 0.05
    sig = family_spread_state(df, mode="spike_reversion", norm_window=240)
    assert not ({s.time for s in sig} & {df.index[i] for i in jumps})


# --------------------------------------------------------------------------- counterfactual
def _flat_bars(n: int = 120) -> pd.DataFrame:
    idx = pd.date_range("2025-03-03", periods=n, freq="h", tz="UTC")
    df = pd.DataFrame({"open": 100.0, "high": 100.2, "low": 99.8, "close": 100.0}, index=idx)
    df.index.name = "time"
    return df


def test_counterfactual_prices_a_bracket_the_market_offered() -> None:
    """A buy stop at 101 with stop 100 / target 103; price runs through 101 then 103."""
    df = _flat_bars()
    when = df.index[40]
    for k, i in enumerate(range(45, 60)):
        lvl = 100.5 + 0.35 * k
        df.iloc[i, df.columns.get_loc("open")] = lvl - 0.1
        df.iloc[i, df.columns.get_loc("close")] = lvl
        df.iloc[i, df.columns.get_loc("high")] = lvl + 0.2
        df.iloc[i, df.columns.get_loc("low")] = lvl - 0.2
    out = cfm.counterfactual(df, when, "buy_stop", 101.0, 100.0, 103.0)
    assert out["status"] == "REPLAYED", out
    assert out["r"] > 0.0
    assert "fill_time" in out and "exit_reason" in out


def test_counterfactual_never_counts_an_unoffered_bracket_as_zero() -> None:
    df = _flat_bars()
    out = cfm.counterfactual(df, df.index[40], "sell_stop", 95.0, 96.0, 93.0)
    assert out["status"] == cfm.NOT_TRIGGERED
    assert "r" not in out


def test_counterfactual_is_pending_until_the_bars_arrive() -> None:
    df = _flat_bars()
    out = cfm.counterfactual(df, df.index[-3], "buy_stop", 101.0, 100.0, 103.0)
    assert out["status"] == cfm.PENDING


def test_counterfactual_refuses_to_price_without_a_stop() -> None:
    df = _flat_bars()
    df.iloc[45:50, df.columns.get_loc("high")] = 101.5
    out = cfm.counterfactual(df, df.index[40], "buy_stop", 101.0, None, None)
    assert out["status"] == "UNPRICED"


def test_filter_value_excludes_untriggered_and_signs_the_avoided_pnl(tmp_path, monkeypatch) -> None:
    """Two vetoed brackets that would have LOST 1R each: the filter earned +2R. One that never
    triggered contributes nothing either way."""
    monkeypatch.setattr(cfm, "DECISIONS", tmp_path / "decisions.jsonl")
    monkeypatch.setattr(cfm, "OUT", tmp_path / "cf.jsonl")
    monkeypatch.setattr(cfm, "REPORT", tmp_path / "FILTER_VALUE.json")
    rows = [{"sleeve": "s", "symbol": "X", "side": "buy_stop", "time": f"t{i}",
             "reason": "regime_hibernate", "status": "REPLAYED", "r": -1.0} for i in range(2)]
    rows.append({"sleeve": "s", "symbol": "X", "side": "sell_stop", "time": "t9",
                 "reason": "regime_hibernate", "status": cfm.NOT_TRIGGERED})
    (tmp_path / "cf.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", "utf-8")
    monkeypatch.setattr(cfm, "_rows", lambda p: (
        [] if p == cfm.DECISIONS else [json.loads(x) for x in p.read_text().splitlines()]))
    doc = cfm.run()
    f = doc["filters"]["regime_hibernate"]
    assert f["n_vetoed_and_triggered"] == 2
    assert f["filter_value_r"] == pytest.approx(2.0)
    assert f["verdict"] == "UNDETERMINED"          # n < 20: no verdict on two trades
    assert doc["not_triggered_total"] == 1


# --------------------------------------------------------------------------- gateway ledger
def _gw_exec(names: tuple[str, ...], consts: tuple[str, ...], ns: dict) -> dict:
    keep = [n for n in _GW_TREE.body
            if (isinstance(n, ast.FunctionDef) and n.name in names)
            or (isinstance(n, ast.Assign) and any(getattr(t, "id", "") in consts
                                                  for t in n.targets))]
    exec(compile(ast.Module(body=keep, type_ignores=[]), "<gw>", "exec"), ns)
    return ns


def _gw_ns(tmp_path: Path) -> dict:
    logs: list[str] = []
    ns: dict = {"json": json, "pd": pd, "np": np, "datetime": datetime, "UTC": UTC,
                "timedelta": timedelta, "log": logs.append, "_logs": logs,
                "now": lambda: "2026-09-04T07:05:00+00:00", "_state_vector_id": lambda: "sv1",
                "_release_id": lambda: "rel1",
                "DECISIONS": tmp_path / "decision_ledger.jsonl", "BASE": tmp_path}
    return _gw_exec(("_record_decision", "_record_vetoed_bracket", "day_range", "bracket_spec"),
                    ("ATR_N", "RR"), ns)


def _last_day_bars(hours: range, day: str = "2026-09-04") -> pd.DataFrame:
    prev = pd.date_range("2026-09-03", periods=24, freq="h", tz="UTC")
    cur = pd.DatetimeIndex([pd.Timestamp(f"{day}T{h:02d}:00:00Z") for h in hours])
    idx = prev.append(cur)
    n = len(idx)
    base = 3000.0 + np.linspace(0, 10, n)
    return pd.DataFrame({"open": base, "high": base + 3.0, "low": base - 3.0, "close": base},
                        index=idx)


def test_record_decision_appends_one_json_line_with_the_state_vector(tmp_path) -> None:
    ns = _gw_ns(tmp_path)
    ns["_record_decision"](sleeve="gold_asia", symbol="XAUUSD", side="buy_stop", lot=0.1,
                           price=1.0, sl=0.5, tp=2.0, taken=False, reason="margin_guard")
    rows = [json.loads(x) for x in (tmp_path / "decision_ledger.jsonl").read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["reason"] == "margin_guard" and rows[0]["taken"] is False
    assert rows[0]["state_vector_id"] == "sv1" and rows[0]["time"]


def test_record_decision_never_raises(tmp_path) -> None:
    ns = _gw_ns(tmp_path)
    ns["DECISIONS"] = tmp_path / "no_such_dir_is_a_file" / "x.jsonl"
    (tmp_path / "no_such_dir_is_a_file").write_text("not a dir")
    ns["_record_decision"](sleeve="s", reason="x")               # must not raise
    assert any("decision record failed" in m for m in ns["_logs"])


def test_vetoed_bracket_records_both_levels_the_veto_refused(tmp_path) -> None:
    ns = _gw_ns(tmp_path)
    df = _last_day_bars(range(0, 8))
    sym = SimpleNamespace(trade_tick_size=0.01, trade_stops_level=20)
    s = {"name": "gold_asia", "symbol": "XAUUSD", "rng": None, "sig_hour": 7}
    assert ns["_record_vetoed_bracket"](s, df, sym, "regime_hibernate", "monitor said so")
    rows = [json.loads(x) for x in (tmp_path / "decision_ledger.jsonl").read_text().splitlines()]
    assert [r["side"] for r in rows] == ["buy_stop", "sell_stop"]
    hi, lo = ns["day_range"](df, None, 7)
    assert rows[0]["price"] == hi and rows[1]["price"] == lo
    for r in rows:
        assert r["taken"] is False and r["reason"] == "regime_hibernate"
        assert r["detail"] == "monitor said so"
        assert np.isfinite(r["sl"]) and np.isfinite(r["tp"]) and r["sl"] != r["price"]
    assert rows[0]["sl"] < hi < rows[0]["tp"]
    assert rows[1]["tp"] < lo < rows[1]["sl"]


def test_vetoed_bracket_waits_when_the_range_is_not_formed(tmp_path) -> None:
    ns = _gw_ns(tmp_path)
    df = _last_day_bars(range(9, 12))                              # no hours before sig_hour
    sym = SimpleNamespace(trade_tick_size=0.01, trade_stops_level=20)
    s = {"name": "gold_asia", "symbol": "XAUUSD", "rng": None, "sig_hour": 7}
    assert ns["_record_vetoed_bracket"](s, df, sym, "state_gate") is False
    assert not (tmp_path / "decision_ledger.jsonl").exists()


def test_every_veto_site_in_the_gateway_writes_the_ledger() -> None:
    """Static: each named reason appears as a `_record_decision`/`_record_vetoed_bracket` call,
    so a filter cannot exist without a line the counterfactual can price."""
    for reason in ("shadow_not_armed", "entry_inside_freeze_band", "margin_guard",
                   "broker_rejected", "placed", "regime_hibernate", "state_gate"):
        assert f'"{reason}"' in _GW_SRC, reason
    assert "_hibernated = [s for s in sleeves if s[\"name\"] in reg_killed]" in _GW_SRC
    # The hibernate pass is read-only against the broker: no order_send on that path.
    start = _GW_SRC.index("THE HIBERNATE VETO'S LEDGER LINE")
    end = _GW_SRC.index("housekeeping: expire stale brackets", start)
    assert "order_send" not in _GW_SRC[start:end]


# --------------------------------------------------------------------------- alpha genome
def test_genome_clusters_edges_that_lose_together() -> None:
    g = {"a": {"symbol": "EURUSD", "legs": ["EUR", "USD"], "mechanism": "breakout",
               "direction_bias": "with", "clock": "asia", "factor_roles": []},
         "b": {"symbol": "GBPUSD", "legs": ["GBP", "USD"], "mechanism": "breakout",
               "direction_bias": "with", "clock": "asia", "factor_roles": []},
         "c": {"symbol": "XAUUSD", "legs": ["USD"], "mechanism": "reversion",
               "direction_bias": "against", "clock": "asia", "factor_roles": ["GOLD"]},
         "d": {"symbol": "AUDJPY", "legs": ["AUD", "JPY"], "mechanism": "breakout",
               "direction_bias": "with", "clock": "london", "factor_roles": []}}
    cl = alpha_genome.cluster(g)
    members = {frozenset(v) for v in cl.values()}
    assert frozenset({"a", "b"}) in members          # same mechanism/bias/clock, share USD
    assert frozenset({"c"}) in members               # different mechanism
    assert frozenset({"d"}) in members               # different clock
    assert len(cl) == 3


def test_unregistered_family_is_reported_not_guessed() -> None:
    assert alpha_genome.MECHANISM_CLASS.get("no_such_family", "UNCLASSIFIED") == "UNCLASSIFIED"
    assert "session_range_breakout" in alpha_genome.MECHANISM_CLASS


# --------------------------------------------------------------------------- opportunity curve
def _phase_trades() -> list[Trade]:
    rng = np.random.default_rng(1)
    out = []
    for i in range(30):                                            # ASIA_OPEN, pays
        out.append(Trade("S1", f"2026-03-{1 + i % 27:02d}T01:00:00+00:00",
                         0.5 + rng.normal(scale=0.1), {}))
    for i in range(12):                                            # NY_CLOSE, loses
        out.append(Trade("S2", f"2026-03-{1 + i % 27:02d}T19:00:00+00:00",
                         -0.4 + rng.normal(scale=0.1), {}))
    for i in range(3):                                             # LONDON_OPEN, too few
        out.append(Trade("S3", f"2026-03-{1 + i:02d}T08:00:00+00:00", -0.9, {}))
    return out


def test_dead_is_measured_and_negative_never_merely_unmeasured() -> None:
    hours, phases = oc.curve(_phase_trades(), off=None)
    assert phases["ASIA_OPEN"]["verdict"] == oc.ALIVE
    assert phases["NY_CLOSE"]["verdict"] == oc.DEAD
    assert phases["LONDON_OPEN"]["verdict"] == oc.UNMEASURED     # 3 trades at -0.9R is not dead
    assert phases["ROLL_THIN"]["verdict"] == oc.UNMEASURED
    tasks = oc.instructions(phases, "UTC")
    assert [t["phase"] for t in tasks] == ["NY_CLOSE"]
    assert tasks[0]["kind"] == "dead_phase" and tasks[0]["source"] == "opportunity_curve"
    assert hours[1]["n_trades"] == 30 and hours[19]["phase"] == "NY_CLOSE"


def test_broker_offset_moves_trades_between_phases() -> None:
    _, utc = oc.curve(_phase_trades(), off=None)
    _, broker = oc.curve(_phase_trades(), off=3)
    assert utc["ASIA_OPEN"]["n_trades"] == 30 and broker["ASIA_OPEN"]["n_trades"] == 0
    assert broker["ASIA_MID"]["n_trades"] == 30                  # 01:00 UTC is 04:00 broker


# --------------------------------------------------------------------------- capability graph
_MOD = "libs/data/pit.py"                      # any real module with no path literals in it


def test_graph_refuses_a_producer_nobody_reads() -> None:
    nodes = (cg.Node("lonely", _MOD, writes=("desks/mt5/reports/nobody.json",)),)
    out = cg.check(nodes)
    checks = {f["check"] for f in out["fatal"]}
    assert "DEAD_PRODUCER" in checks and "ADVISORY_ONLY" in checks and not out["ok"]


def test_graph_accepts_a_producer_that_reaches_a_decision_in_two_hops() -> None:
    nodes = (cg.Node("finder", _MOD, writes=("desks/mt5/data/a.json",)),
             cg.Node("middle", _MOD, reads=("desks/mt5/data/a.json",),
                     writes=("desks/mt5/data/b.json",)),
             cg.Node("decider", _MOD, reads=("desks/mt5/data/b.json",),
                     writes=("desks/mt5/data/c.json",), authority=("sizing",)),
             cg.Node("reader", _MOD, reads=("desks/mt5/data/c.json",),
                     writes=("desks/mt5/reports/markout.json",)))   # HUMAN_READ artifact
    out = cg.check(nodes)
    assert out["ok"], out["fatal"]


def test_graph_refuses_a_consumer_of_nothing_and_a_missing_module() -> None:
    nodes = (cg.Node("ghost", "libs/does_not_exist.py", reads=("desks/mt5/data/never.json",),
                     writes=("desks/mt5/data/x.json",), authority=("sizing",)),)
    checks = {f["check"] for f in cg.check(nodes)["fatal"]}
    assert {"DEAD_CONSUMER", "MISSING_MODULE"} <= checks


def test_the_desks_real_graph_is_integrated() -> None:
    """Every producer on the desk reaches a decision, every consumer has a producer, and every
    conditioning dimension has been judged. This is the integration theorem as a test."""
    out = cg.check()
    assert out["ok"], json.dumps(out["fatal"], indent=1)
    names = {n.name for n in cg.NODES}
    for must in ("gateway", "counterfactual_markout", "excursions", "alpha_genome",
                 "opportunity_curve", "microstructure_miner", "regime_monitor"):
        assert must in names


def test_the_decision_ledger_is_declared_end_to_end() -> None:
    gw = next(n for n in cg.NODES if n.name == "gateway")
    cf = next(n for n in cg.NODES if n.name == "counterfactual_markout")
    rm = next(n for n in cg.NODES if n.name == "regime_monitor")
    assert "desks/mt5/data/decision_ledger.jsonl" in gw.writes
    assert "desks/mt5/data/decision_ledger.jsonl" in cf.reads
    assert "desks/mt5/reports/FILTER_VALUE.json" in cf.writes
    assert "desks/mt5/reports/FILTER_VALUE.json" in rm.reads      # the veto reads its own value


# --------------------------------------------------------------------------- point in time
def test_stamp_keeps_the_producers_availability_and_hashes_the_body() -> None:
    row = {"title": "x", "found_at": "2026-01-02T03:04:05+00:00", "symbol": "XAUUSD"}
    s = pit.stamp(row, "test_source", source_version="v1",
                  now=datetime(2026, 5, 1, tzinfo=UTC))
    assert s["available_time"] == "2026-01-02T03:04:05+00:00"       # never overwritten
    assert s["ingested_time"].startswith("2026-05-01")
    assert s["source_version"] == "v1" and pit.is_stamped(s)
    assert s["payload_hash"] == pit.payload_hash(s)
    again = pit.stamp(row, "test_source", source_version="v2",
                      now=datetime(2026, 6, 1, tzinfo=UTC))
    assert again["payload_hash"] == s["payload_hash"]       # same finding, same hash, any stamp
    assert pit.stamp({**row, "title": "y"}, "t")["payload_hash"] != s["payload_hash"]
    assert pit.payload_hash({**row}) == pit.payload_hash({**row, "payload_hash": "zz"})


def test_unstamped_rows_are_usable_at_no_time() -> None:
    assert not pit.usable_at({"found_at": "2020-01-01T00:00:00+00:00"},
                             datetime(2030, 1, 1, tzinfo=UTC))
    s = pit.stamp({"found_at": "2026-01-02T00:00:00+00:00"}, "t", source_version="v")
    assert pit.usable_at(s, datetime(2026, 1, 2, 0, 0, 1, tzinfo=UTC))
    assert not pit.usable_at(s, datetime(2026, 1, 1, tzinfo=UTC))


def test_census_counts_stamped_fraction() -> None:
    rows = [pit.stamp({"a": 1}, "t", source_version="v"), {"a": 2}, "not a row"]
    c = pit.census(rows)
    assert c["rows"] == 2 and c["stamped"] == 1 and c["stamped_frac"] == 0.5


# --------------------------------------------------------------------------- broker clock
def test_broker_clock_is_recorded_once_and_refreshed_on_change(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(session_phase, "BROKER_CLOCK", tmp_path / "broker_clock.json")
    session_phase._record_broker_clock(3)
    rec = json.loads((tmp_path / "broker_clock.json").read_text())
    assert rec["utc_offset_hours"] == 3 and rec["source"] == "live_terminal"
    session_phase._record_broker_clock(3)
    assert json.loads((tmp_path / "broker_clock.json").read_text())["measured_at"] == \
        rec["measured_at"]                                          # same value, same day: kept
    session_phase._record_broker_clock(2)
    assert json.loads((tmp_path / "broker_clock.json").read_text())["utc_offset_hours"] == 2


@pytest.mark.skipif(importlib.util.find_spec("MetaTrader5") is not None,
                    reason="a live terminal answers first on this host")
def test_hosts_without_a_terminal_inherit_the_recorded_clock(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(session_phase, "BROKER_CLOCK", tmp_path / "broker_clock.json")
    assert session_phase.broker_utc_offset_h() == (None, "unknown")
    session_phase._record_broker_clock(3)
    assert session_phase.broker_utc_offset_h() == (3, "recorded_broker_clock")


# --------------------------------------------------------------------------- queue ownership
def test_feedback_engines_own_only_their_own_queue_rows(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(regime_coverage, "QUEUE", tmp_path / "q.json")
    regime_coverage._merge_into_queue([{"source": "regime_coverage", "title": "a"}])
    regime_coverage._merge_into_queue([{"source": "opportunity_curve", "title": "b"}],
                                      source="opportunity_curve")
    regime_coverage._merge_into_queue([{"source": "regime_coverage", "title": "a2"}])
    rows = json.loads((tmp_path / "q.json").read_text())["tasks"]
    assert sorted(r["title"] for r in rows) == ["a2", "b"]


def test_cluster_coverage_names_the_mechanisms_never_tried_in_a_state() -> None:
    cmap = {("XAUUSD", "fam0"): "breakout/with/asia/USD", ("XAUUSD", "fam1"): "reversion/against/asia/USD"}
    assert regime_coverage._cluster_of("XAUUSD_fam0_asia", cmap) == "breakout/with/asia/USD"
    trades = [Trade("XAUUSD_fam0_asia", "t", 0.1, {"global": "A"}) for _ in range(20)]
    trades += [Trade("XAUUSD_fam1_asia", "t", 0.1, {"global": "B"}) for _ in range(20)]
    cov = regime_coverage.coverage(trades, ("global",), cmap)
    assert cov["global=A"]["clusters_never_tried_here"] == ["reversion/against/asia/USD"]
    assert cov["global=B"]["clusters_tried"] == ["reversion/against/asia/USD"]


def test_a_gap_the_desks_own_ledgers_found_is_worked_before_a_crawler_row(monkeypatch) -> None:
    from libs.research import bandit
    monkeypatch.setattr(bandit, "shares", lambda: {a: 1.0 / len(bandit.ARMS) for a in bandit.ARMS})
    tasks = [{"source": "crawler", "title": "some web row", "id": "z1"},
             {"source": "opportunity_curve", "kind": "dead_phase", "title": "dead NY_CLOSE",
              "id": "z2"},
             {"source": "excursions", "kind": "exit_hypothesis", "title": "exit", "id": "z3"}]
    order = [t["source"] for t in deepening_worker.voi_order(tasks)]
    assert order.index("opportunity_curve") < order.index("excursions") < order.index("crawler")
    assert "dead_phase" in deepening_worker._SYSTEM_BY_KIND
    assert "exit_hypothesis" in deepening_worker._SYSTEM_BY_KIND
