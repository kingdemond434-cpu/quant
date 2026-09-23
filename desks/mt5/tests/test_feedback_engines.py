"""Exit accounts, action counterfactuals, research P&L: the three feedback engines, off-box.

What is pinned:

  * exit attribution joins each ledger trade to its excursion and names WHICH exit reason gave
    the excursion back -- a near target, a binding time stop, a barely-touched stop -- with a
    verdict only at 20 joined trades, UNMEASURED_PATH when the path ledger has none, and the
    give-back priced as dE[log W] at the allocator's weight (an upper bound, in R when unfunded);
  * the taken-trade counterfactual ledger is append-only and keyed, prices holds with the 1R
    stop kept, computes sizing growth as E[log(1 + k h r)] and never linearly, and only speaks
    at n >= 30 with |t| >= 2 -- SIZE_UP_EARNS is the second governance rule as a measurement;
  * research P&L attributes book growth to the certificate's source, aliases the canon's
    `external_discoveries` to the graph's `external`, credits unattributed growth to nobody,
    floors every worth at 0.25, and writes a per-arm worth the bandit's `evidence` can consume;
  * both sizing/exit modules carry the two governance rules verbatim, and none of the three
    names a crypto exchange.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research import bandit  # noqa: E402
from research import action_counterfactuals as ac  # noqa: E402
from research import exit_accounts as ea  # noqa: E402
from research import regime_coverage  # noqa: E402
from research import research_pnl as rp  # noqa: E402

RULE_1 = "Every risk reduction mechanism must prove that it increases robust forward E[log W]."
RULE_2 = ("Every strong opportunity must be allowed to increase capital above normal when the "
          "evidence supports it.")


# --------------------------------------------------------------------------- helpers
def _stamp(i: int) -> str:
    return str(pd.Timestamp("2026-03-02T00:00:00Z") + pd.Timedelta(hours=i))


def _ledger(tmp_path: Path, sleeve: str, rows: list[dict]) -> None:
    d = tmp_path / "ledgers"
    d.mkdir(exist_ok=True)
    (d / f"ledger_{sleeve}.json").write_text(json.dumps(rows), "utf-8")


def _trade(i: int, r: float, reason: str, side: int = 1, entry: float = 1.0,
           risk: float = 0.01) -> dict:
    return {"entry_time": _stamp(i), "exit_time": _stamp(i + 2), "side": side, "entry": entry,
            "exit": entry + side * r * risk, "r_multiple": r, "reason": reason,
            "phase": "forward"}


def _excursion(sleeve: str, t: dict, mfe: float, mae: float) -> dict:
    return {"sleeve": sleeve, "symbol": sleeve.split("_")[0], "entry_time": t["entry_time"],
            "exit_time": t["exit_time"], "side": t["side"], "r_multiple": t["r_multiple"],
            "mfe_r": mfe, "mae_r": mae, "bars": 3}


def _patch_exit(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ea, "LEDGER_DIRS", (tmp_path / "ledgers",))
    monkeypatch.setattr(ea, "EXCURSIONS", tmp_path / "excursions.jsonl")
    monkeypatch.setattr(ea, "LIVE", tmp_path / "live_ledger.jsonl")
    monkeypatch.setattr(ea, "FORECASTS", tmp_path / "pf_forecast_log.jsonl")
    monkeypatch.setattr(ea, "REPORT", tmp_path / "EXIT_ACCOUNTS.json")
    monkeypatch.setattr(regime_coverage, "QUEUE", tmp_path / "queue.json")


def _patch_cf(monkeypatch, tmp_path: Path, bars: pd.DataFrame | None) -> None:
    monkeypatch.setattr(ac, "LEDGER_DIRS", (tmp_path / "ledgers",))
    monkeypatch.setattr(ac, "LIVE", tmp_path / "live_ledger.jsonl")
    monkeypatch.setattr(ac, "FORECASTS", tmp_path / "pf_forecast_log.jsonl")
    monkeypatch.setattr(ac, "OUT", tmp_path / "action_counterfactuals.jsonl")
    monkeypatch.setattr(ac, "REPORT", tmp_path / "ACTION_COUNTERFACTUALS.json")
    monkeypatch.setattr(ac, "_load_bars", lambda sym: bars)
    monkeypatch.setattr(regime_coverage, "QUEUE", tmp_path / "queue.json")


def _forecast(tmp_path: Path, book: dict[str, float], elog: float = 0.004,
              heat: float | None = None) -> None:
    line = {"t": "2026-03-10T03:00:00+00:00", "total_heat": heat or sum(book.values()),
            "expected_log_per_day": elog, "book": book}
    (tmp_path / "pf_forecast_log.jsonl").write_text(
        json.dumps({"t": "old", "book": {}}) + "\n" + json.dumps(line) + "\n", "utf-8")


def _exit_world(tmp_path: Path) -> None:
    """Six sleeves, one per verdict, with the excursion rows that make each verdict true."""
    rng = np.random.default_rng(0)
    exc: list[dict] = []

    def add(sleeve: str, trades: list[tuple[float, str, float, float]], joined: bool = True):
        rows = []
        for i, (r, reason, mfe, mae) in enumerate(trades):
            t = _trade(i * 3, r, reason)
            rows.append(t)
            if joined:
                exc.append(_excursion(sleeve, t, mfe, mae))
        _ledger(tmp_path, sleeve, rows)

    noise = lambda: float(rng.normal(scale=0.02))  # noqa: E731
    # TARGET_TOO_NEAR: targets bank ~1R on trades whose median excursion is 2.2R.
    add("EURUSD_fam_asia", [(1.0 + noise(), "target", 2.2 + noise(), 0.3) for _ in range(30)]
        + [(-1.0 + noise(), "stop", 0.1, 1.1) for _ in range(10)])
    # TIME_STOP_BINDS: ttl exits keep +0.4R of a 1.5R median excursion.
    add("GBPUSD_fam_asia", [(0.4 + noise(), "ttl", 1.5 + noise(), 0.4) for _ in range(25)])
    # STOP_TOO_TIGHT: stops barely exceeded (MAE 1.15 vs |R| 1.05) after a +0.8R excursion.
    add("USDJPY_fam_asia", [(-1.05 + noise(), "stop", 0.8, 1.15) for _ in range(20)]
        + [(1.0 + noise(), "target", 1.1, 0.2) for _ in range(4)])
    # UNMEASURED: ten trades.
    add("AUDUSD_fam_asia", [(1.0 + noise(), "target", 2.5, 0.2) for _ in range(10)])
    # UNMEASURED_PATH: enough trades, no excursion rows.
    add("NZDUSD_fam_asia", [(1.0 + noise(), "target", 2.5, 0.2) for _ in range(25)], joined=False)
    # AS_IS: targets at 1R on a 1.2R excursion, a few stops, nothing binding.
    add("EURGBP_fam_asia", [(1.0 + noise(), "target", 1.2 + noise(), 0.3) for _ in range(24)]
        + [(-1.0 + noise(), "stop", 0.1, 1.6) for _ in range(6)])
    (tmp_path / "excursions.jsonl").write_text(
        "\n".join(json.dumps(e) for e in exc) + "\n", "utf-8")
    _forecast(tmp_path, {"EURUSD_fam_asia": 0.02, "GBPUSD_fam_asia": 0.01})


# --------------------------------------------------------------------------- exit accounts
def test_exit_accounts_names_the_reason_that_gave_the_excursion_back(tmp_path, monkeypatch):
    _patch_exit(monkeypatch, tmp_path)
    _exit_world(tmp_path)
    doc = ea.run()
    v = {s: d["verdict"] for s, d in doc["sleeves"].items()}
    assert v["EURUSD_fam_asia"] == ea.TARGET_TOO_NEAR
    assert v["GBPUSD_fam_asia"] == ea.TIME_STOP_BINDS
    assert v["USDJPY_fam_asia"] == ea.STOP_TOO_TIGHT
    assert v["AUDUSD_fam_asia"] == ea.UNMEASURED
    assert v["NZDUSD_fam_asia"] == ea.UNMEASURED_PATH
    assert v["EURGBP_fam_asia"] == ea.AS_IS
    eu = doc["sleeves"]["EURUSD_fam_asia"]
    assert eu["n_joined"] == 40 and eu["implied_target_r"] == pytest.approx(1.0, abs=0.05)
    assert eu["by_reason"]["target"]["n"] == 30 and eu["by_reason"]["stop"]["n"] == 10
    assert eu["by_reason"]["target"]["capture_ratio"] == pytest.approx(1.0 / 2.2, abs=0.05)
    assert eu["by_reason"]["target"]["mean_left_on_table_r"] == pytest.approx(1.2, abs=0.05)
    assert eu["t_r"] is not None and "median MFE" in eu["why"]
    assert (tmp_path / "EXIT_ACCOUNTS.json").exists()
    assert doc["gaps"]["live_ledger"].startswith("absent")


def test_exit_decomposition_is_captured_left_and_survived():
    d = ea.decompose({"r_multiple": 0.7, "mfe_r": 1.9, "mae_r": 0.4})
    assert d == {"captured_r": 0.7, "left_on_table_r": 1.2, "adverse_survived_r": 0.4}
    assert ea.decompose({"r_multiple": 1.5, "mfe_r": 1.5, "mae_r": 0.2})["left_on_table_r"] == 0.0
    assert ea.decompose({"r_multiple": -1.0, "mfe_r": 0.0, "mae_r": 1.2})["left_on_table_r"] == 1.0


def test_give_back_is_priced_as_delta_elogw_at_the_allocators_weight(tmp_path, monkeypatch):
    """The exact log difference is below the linear h x left (concavity), in log-wealth units
    when the allocator funds the sleeve, and in R -- said so -- when it does not."""
    _patch_exit(monkeypatch, tmp_path)
    _exit_world(tmp_path)
    g = ea.run()["growth_left_on_table"]
    eu = g["EURUSD_fam_asia"]
    assert eu["allocator_weight_h"] == 0.02 and eu["units"].startswith("log-wealth")
    assert 0 < eu["delta_elogw_per_trade"] < eu["delta_elogw_linear"]
    assert eu["delta_elogw_linear"] == pytest.approx(0.02 * eu["mean_left_on_table_r"], rel=1e-6)
    assert eu["delta_elogw_per_day"] is not None and eu["bound"].startswith("upper")
    nz = g["USDJPY_fam_asia"]                      # not in the book
    assert nz["units"] == "R" and nz["delta_elogw_per_trade"] is None
    assert nz["mean_left_on_table_r"] > 0
    assert g["NZDUSD_fam_asia"]["why"] == "no excursion path joined"


def test_exit_accounts_writes_only_its_own_queue_rows_and_never_an_entry(tmp_path, monkeypatch):
    _patch_exit(monkeypatch, tmp_path)
    _exit_world(tmp_path)
    regime_coverage._merge_into_queue([{"source": "excursions", "title": "keep me"}],
                                      source="excursions")
    doc = ea.run()
    tasks = doc["exit_hypotheses"]
    assert sorted(t["sleeve"] for t in tasks) == ["EURUSD_fam_asia", "GBPUSD_fam_asia",
                                                  "USDJPY_fam_asia"]
    for t in tasks:
        assert t["source"] == "exit_accounts" and t["kind"] == "exit_hypothesis"
        assert t["status"] is None and t["symbols"] == [t["sleeve"].split("_")[0]]
        assert t["family"] == "fam" and t["params"] == {}
        assert "n=" in t["description"] and "entry is not changed" in t["description"]
    eu = next(t for t in tasks if t["sleeve"] == "EURUSD_fam_asia")
    assert "dE[log W]" in eu["description"] and "h=0.02" in eu["description"]
    us = next(t for t in tasks if t["sleeve"] == "USDJPY_fam_asia")
    assert "R units" in us["description"]
    q = json.loads((tmp_path / "queue.json").read_text())["tasks"]
    assert sum(1 for r in q if r["source"] == "exit_accounts") == 3
    assert any(r["title"] == "keep me" for r in q)
    ea.run()                                           # a rerun replaces, never accumulates
    q = json.loads((tmp_path / "queue.json").read_text())["tasks"]
    assert sum(1 for r in q if r["source"] == "exit_accounts") == 3


def test_exit_accounts_degrades_with_a_reason_not_silently(tmp_path, monkeypatch):
    _patch_exit(monkeypatch, tmp_path)
    _ledger(tmp_path, "EURUSD_fam_asia", [_trade(i, 1.0, "target") for i in range(25)]
            + [{"opened_at": _stamp(99), "r": 0.2}])       # a scalp row: R only, no price
    doc = ea.run()
    assert "excursions" in doc["gaps"] and "UNMEASURED_PATH" in doc["gaps"]["excursions"]
    assert doc["sleeves"]["EURUSD_fam_asia"]["verdict"] == ea.UNMEASURED_PATH
    assert doc["gaps"]["unparsed_rows"].startswith("1 ledger rows")
    assert doc["allocator_book"]["source"].startswith("pf_forecast_log absent")
    assert doc["exit_hypotheses"] == []


def test_exit_accounts_reads_both_ledger_dialects():
    assert ea._side(1) == 1 and ea._side(-1) == -1 and ea._side("long") == 1
    assert ea._side(0, "live") == 1 and ea._side(1, "live") == -1     # MT5 position type
    live = ea._trade({"sleeve": "s", "time": _stamp(5), "entry_price": 1.1, "fill_price": 1.2,
                      "r_multiple": 0.5, "side": 0, "reason": "target"}, "s", "live")
    assert live is None, "a live row without an entry_time cannot be joined to a path"
    live = ea._trade({"entry_time": _stamp(1), "time": _stamp(5), "entry_price": 1.1,
                      "r_multiple": 0.5, "side": 1}, "s", "live")
    assert live["side"] == -1 and live["exit_time"] == _stamp(5) and live["reason"] == "other"


# --------------------------------------------------------------------------- counterfactuals
def _trend_bars(n: int = 400, drift: float = 0.05, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-03-02", periods=n, freq="h", tz="UTC")
    close = 100.0 + np.cumsum(drift + rng.normal(scale=0.03, size=n))
    df = pd.DataFrame({"open": np.r_[close[0], close[:-1]], "high": close + 0.02,
                       "low": close - 0.02, "close": close}, index=idx)
    df.index.name = "time"
    return df


def _cf_world(tmp_path: Path, bars: pd.DataFrame, n: int = 40) -> None:
    """Longs that exited two bars after entry on a trend that ran for forty-eight."""
    rows = []
    for k in range(n):
        i = 5 + 3 * k
        entry, exit_ = float(bars["close"].iloc[i]), float(bars["close"].iloc[i + 2])
        rows.append({"entry_time": str(bars.index[i]), "exit_time": str(bars.index[i + 2]),
                     "side": 1, "entry": entry, "exit": exit_, "r_multiple": exit_ - entry,
                     "reason": "ttl"})                        # risk = 1.0 price unit
    _ledger(tmp_path, "EURUSD_fam_asia", rows)
    # A loser whose smaller size earns: shorts on the same uptrend, exited after two bars.
    rows = []
    for k in range(n):
        i = 5 + 3 * k
        entry, exit_ = float(bars["close"].iloc[i]), float(bars["close"].iloc[i + 2])
        rows.append({"entry_time": str(bars.index[i]), "exit_time": str(bars.index[i + 2]),
                     "side": -1, "entry": entry, "exit": exit_, "r_multiple": entry - exit_,
                     "reason": "ttl"})
    _ledger(tmp_path, "GBPUSD_fam_asia", rows)
    _forecast(tmp_path, {"EURUSD_fam_asia": 0.02})


def test_hold_alternatives_keep_the_stop_and_price_the_close():
    df = _trend_bars(drift=0.0, seed=1)
    entry = float(df["close"].iloc[10])
    df.iloc[13, df.columns.get_loc("low")] = entry - 2.5      # the stop is hit on bar +3
    df.iloc[50:70, df.columns.get_loc("close")] = entry + 5.0
    df.iloc[50:70, df.columns.get_loc("high")] = entry + 5.02
    cf = ac.counterfactual_path(df, str(df.index[10]), str(df.index[12]), 1, entry, 1.0)
    assert cf["bars_held"] == 2 and cf["stop_hit_bar"] == 3
    assert cf["hold"]["1"] == pytest.approx((df["close"].iloc[11] - entry), abs=1e-4)
    assert cf["hold"]["6"] == -1.0 and cf["hold"]["48"] == -1.0, "a breached stop is -1R, not +5R"
    # A short on the same bars: the dip is favourable, so no stop; +48 sits at the rally.
    cf = ac.counterfactual_path(df, str(df.index[10]), str(df.index[12]), -1, entry, 1.0)
    assert cf["stop_hit_bar"] is not None and cf["hold"]["48"] == -1.0    # +5 rally = short's stop
    assert ac.counterfactual_path(df, str(df.index[-10]), str(df.index[-8]), 1, entry, 1.0) \
        is None, "fewer than 48 bars after entry is PENDING"


def test_sizing_growth_is_the_log_and_never_linear():
    rng = np.random.default_rng(3)
    r = 0.2 + rng.normal(scale=0.5, size=60)
    rows = [{"r_multiple": float(x), "hold": {str(k): float(x) for k in ac.HORIZONS},
             "bars_held": 2, "entry_time": _stamp(i)} for i, x in enumerate(r)]
    h = 0.05
    out = ac.judge(rows, h, "test")
    for k in ac.SIZES:
        assert out["sizing"][f"{k:.1f}x"]["growth"] == pytest.approx(
            float(np.mean(np.log(1.0 + k * h * r))), abs=1e-6)
    g = {k: out["sizing"][f"{k:.1f}x"]["growth"] for k in ac.SIZES}
    assert g[2.0] < 2.0 * g[1.0], "doubling size less than doubles growth"
    assert out["sizing"]["1.0x"]["delta_elogw"] == 0.0
    ruin = ac.judge(rows, 3.0, "test")                       # 3x equity per R: a -1R is ruin
    assert ruin["verdict"] == ac.UNMEASURED and "ruin" in ruin["why"]


def test_counterfactual_ledger_is_append_only_and_verdicts_carry_t_and_n(tmp_path, monkeypatch):
    bars = _trend_bars()
    _patch_cf(monkeypatch, tmp_path, bars)
    _cf_world(tmp_path, bars)
    doc = ac.run()
    assert doc["new_measured"] == 80 and doc["total_measured"] == 80
    eu = doc["sleeves"]["EURUSD_fam_asia"]
    assert eu["n"] == 40 and eu["h"] == 0.02 and eu["h_source"] == "pf_forecast_log book"
    assert eu["verdict"] == ac.HOLD_LONGER and eu["best_alternative"] == "+48 bars"
    assert eu["holds"]["48"]["mean_r"] > 2.0 and eu["holds"]["48"]["t"] > 2.0
    kinds = {c["verdict"] for c in eu["verdicts_all"]}
    assert ac.SIZE_UP in kinds, "a winner with t >> 2 earns more at 1.5x/2.0x: the second rule"
    assert ac.SIZE_DOWN not in kinds and ac.EXIT_EARLIER not in kinds
    assert eu["delta_elogw_per_day"] is not None and eu["median_bars_held"] == 2.0
    gb = doc["sleeves"]["GBPUSD_fam_asia"]
    assert gb["h"] == ac.FALLBACK_H and "fallback" in gb["h_source"]
    kinds = {c["verdict"] for c in gb["verdicts_all"]}
    assert ac.SIZE_DOWN in kinds and ac.SIZE_UP not in kinds
    assert gb["opposite"]["delta_elogw"] > 0                   # the other side was the trade
    for c in eu["verdicts_all"] + gb["verdicts_all"]:
        assert c["t"] >= ac.T_MIN and c["delta_elogw"] > 0
    lines = (tmp_path / "action_counterfactuals.jsonl").read_text().splitlines()
    assert len(lines) == 80
    row = json.loads(lines[0])
    assert row["risk_source"] == "realised_r" and row["risk_price"] == pytest.approx(1.0)
    assert set(row["hold"]) == {"1", "6", "12", "24", "48"} and row["bar_clock"] == "H1"
    again = ac.run()
    assert again["new_measured"] == 0 and again["total_measured"] == 80
    assert len((tmp_path / "action_counterfactuals.jsonl").read_text().splitlines()) == 80


def test_counterfactual_tasks_split_sizing_from_exit_and_measure_only(tmp_path, monkeypatch):
    bars = _trend_bars()
    _patch_cf(monkeypatch, tmp_path, bars)
    _cf_world(tmp_path, bars)
    doc = ac.run()
    tasks = doc["tasks"]
    by = {(t["sleeve"], t["verdict"]): t for t in tasks}
    assert ("EURUSD_fam_asia", ac.HOLD_LONGER) in by and ("EURUSD_fam_asia", ac.SIZE_UP) in by
    assert ("GBPUSD_fam_asia", ac.SIZE_DOWN) in by
    for t in tasks:
        assert t["source"] == "action_counterfactuals" and t["status"] is None
        assert t["kind"] == ("sizing_hypothesis" if t["verdict"].startswith("SIZE")
                             else "exit_hypothesis")
        assert "dE[log W]" in t["description"] and f"n={t['evidence']['n']}" in t["description"]
        assert t["evidence"]["t"] >= 2.0 and t["params"] == {}
    q = json.loads((tmp_path / "queue.json").read_text())["tasks"]
    assert {r["source"] for r in q} == {"action_counterfactuals"} and len(q) == len(tasks)
    # MEASURES ONLY: the report and the ledger are the only things written.
    written = sorted(p.name for p in tmp_path.iterdir() if p.is_file())
    assert written == ["ACTION_COUNTERFACTUALS.json", "action_counterfactuals.jsonl",
                       "pf_forecast_log.jsonl", "queue.json"]


def test_counterfactuals_skip_with_a_reason_and_stay_unmeasured_under_thirty(tmp_path, monkeypatch):
    bars = _trend_bars()
    _patch_cf(monkeypatch, tmp_path, bars)
    _cf_world(tmp_path, bars, n=12)
    _ledger(tmp_path, "xau_m15_anti_momentum", [{"opened_at": _stamp(1), "r": 0.1},
                                                _trade(3, 0.5, "target")])
    i = len(bars) - 5
    _ledger(tmp_path, "USDJPY_fam_asia", [{"entry_time": str(bars.index[i]),
                                          "exit_time": str(bars.index[i + 1]), "side": 1,
                                          "entry": 100.0, "exit": 100.5, "r_multiple": 0.5,
                                          "reason": "target"},
                                         {"entry_time": _stamp(2), "exit_time": _stamp(3),
                                          "side": 1, "entry": 100.0, "exit": 100.0,
                                          "r_multiple": 0.0, "reason": "ttl"}])
    doc = ac.run()
    assert doc["skipped"] == {"sub_h1_sleeve": 1, "pending": 1, "no_risk_scale": 1}
    assert doc["gaps"]["unparsed_rows"].startswith("1 ledger rows")
    assert doc["sleeves"]["EURUSD_fam_asia"]["verdict"] == ac.UNMEASURED
    assert "30 needed" in doc["sleeves"]["EURUSD_fam_asia"]["why"]
    assert doc["tasks"] == [] and doc["verdicts"][ac.UNMEASURED] == 2
    monkeypatch.setattr(ac, "_load_bars", lambda sym: None)
    _ledger(tmp_path, "NZDUSD_fam_asia", [_trade(9, 0.5, "target")])
    # The new sleeve AND the still-pending trade, which is re-tried until it is measured.
    assert ac.run()["skipped"] == {"sub_h1_sleeve": 1, "no_risk_scale": 1, "no_bars": 2}


# --------------------------------------------------------------------------- research P&L
def _pnl_world(tmp_path: Path, monkeypatch) -> None:
    from libs.research.hypothesis_graph import CERTIFIED, FAILED, Graph, Node
    g = Graph(tmp_path / "graph.jsonl")
    for i in range(10):
        g.append(Node("EURUSD", "session_range_breakout", {"rr": i}, source="external",
                      fate=FAILED))
    for i in range(2):
        g.append(Node("EURUSD", "session_range_breakout", {"wb": i}, source="external",
                      fate=CERTIFIED))
    g.append(Node("USDJPY", "carry", {"k": 1}, source="external", fate=FAILED))
    g.append(Node("USDJPY", "carry", {"k": 1}, source="external", fate=CERTIFIED))  # last wins
    for i in range(5):
        g.append(Node("XAUUSD", "cross_asset_residual", {"z": i}, source="fund_playbook:AQR:A"))
    monkeypatch.setattr(rp, "_graph_rows", lambda: (g.rows(), None))
    canon = {"survivors": {
        "external.EURUSD.session_range_breakout": {
            "sym": "EURUSD", "hunt": "external_discoveries",
            "shadow_spec": {"symbol": "EURUSD", "family": "session_range_breakout",
                            "selector": "asia", "condition": None}},
        "external.EURUSD.session_range_breakout.rr=1.5": {
            "sym": "EURUSD", "hunt": "external_discoveries",
            "shadow_spec": {"symbol": "EURUSD", "family": "session_range_breakout",
                            "selector": "asia", "condition": None}},
        "external.XAUUSD.session_range_breakout": {
            "sym": "XAUUSD", "hunt": "external_discoveries",
            "shadow_spec": {"symbol": "XAUUSD", "family": "session_range_breakout",
                            "selector": "asia", "condition": None}},
        "qquant.hunt16.json.AUDNZD dav": {
            "sym": "AUDNZD", "hunt": "hunt16.json",
            "shadow_spec": {"symbol": "AUDNZD", "family": "dav", "selector": "afternoon",
                            "condition": "NORMAL_DAY"}},
        "not a cert": 3}}
    (tmp_path / "canon.json").write_text(json.dumps(canon), "utf-8")
    monkeypatch.setattr(rp, "CANON", tmp_path / "canon.json")
    monkeypatch.setattr(rp, "FORECASTS", tmp_path / "pf_forecast_log.jsonl")
    monkeypatch.setattr(rp, "REPORT", tmp_path / "RESEARCH_PNL.json")
    monkeypatch.setattr(rp, "MARGINAL", tmp_path / "research_marginal.json")
    _forecast(tmp_path, {"EURUSD_asia": 0.10, "gold_asia": 0.03,
                         "AUDNZD_dav_afternoon_NORMAL_DAY": 0.05, "MYSTERY_x_asia": 0.02},
              elog=0.004, heat=0.2)


def test_research_pnl_joins_trials_to_the_growth_their_certificates_carry(tmp_path, monkeypatch):
    _pnl_world(tmp_path, monkeypatch)
    doc = rp.run()
    ext = doc["sources"]["external"]
    assert (ext["trials"], ext["failed"], ext["certified"]) == (13, 10, 3)
    assert ext["arm"] == "external_screen"
    assert ext["growth_per_day"] == pytest.approx(0.004 * (0.10 + 0.03) / 0.2, abs=1e-9)
    assert ext["cost_unit_per_trial"] == sum(bandit.COST["external_screen"])
    assert ext["cost_units"] == 13 * sum(bandit.COST["external_screen"])
    assert ext["roi_growth_per_cost_unit"] == pytest.approx(
        ext["growth_per_day"] / ext["cost_units"], rel=1e-6)
    assert ext["growth_per_certificate"] == pytest.approx(ext["growth_per_day"] / 3, abs=1e-8)
    aqr = doc["sources"]["fund_playbook:AQR:A"]
    assert (aqr["trials"], aqr["certified"], aqr["growth_per_day"]) == (5, 0, 0.0)
    assert aqr["roi_growth_per_cost_unit"] == 0.0 and aqr["growth_per_certificate"] is None
    h16 = doc["sources"]["hunt16.json"]
    assert h16["trials"] == 0 and h16["growth_per_day"] == pytest.approx(0.004 * 0.05 / 0.2)
    assert doc["unattributed_growth_per_day"] == pytest.approx(0.004 * 0.02 / 0.2)
    assert doc["unattributed_sleeves"] == ["MYSTERY_x_asia"]
    assert "unknown" not in doc["sources"] and "unknown" not in doc["worth_by_source"]
    assert doc["sleeves"]["EURUSD_asia"]["cert"] == "external.EURUSD.session_range_breakout"
    assert doc["sleeves"]["gold_asia"]["source"] == "external"
    assert doc["arm_fallback_sources"] == ["hunt16.json"]


def test_research_worth_is_normalised_to_mean_one_and_never_below_the_floor(tmp_path, monkeypatch):
    _pnl_world(tmp_path, monkeypatch)
    doc = rp.run()
    w = doc["worth_by_source"]
    assert w["fund_playbook:AQR:A"] == rp.WORTH_FLOOR == 0.25
    assert w["external"] > 1.0 > w["hunt16.json"] > rp.WORTH_FLOOR
    assert (w["external"] + w["hunt16.json"]) / 2 == pytest.approx(1.0, abs=1e-3)
    assert min(w.values()) >= rp.WORTH_FLOOR
    arms = doc["worth_by_arm"]
    assert set(arms) == set(bandit.ARMS) and min(arms.values()) >= rp.WORTH_FLOOR
    assert arms["external_screen"] > 1.0 and arms["new_mechanism"] == rp.WORTH_FLOOR
    assert doc["arms"]["new_mechanism"]["trials"] == 5
    assert doc["arms"]["new_mechanism"]["sources"] == ["fund_playbook:AQR:A"]
    assert "0.25" in doc["research_pnl_note"] and "information value" in doc["research_pnl_note"]
    m = json.loads((tmp_path / "research_marginal.json").read_text())
    assert set(m) >= {"generated_utc", "worth_by_arm", "worth_by_source"}
    assert m["worth_by_arm"] == arms
    # The bandit's evidence() reads exactly this shape, unchanged.
    ev = bandit.evidence([], marginal_by_source=m["worth_by_arm"])
    assert ev["external_screen"]["worth"] == arms["external_screen"]
    assert ev["new_mechanism"]["worth"] == rp.WORTH_FLOOR


def test_research_pnl_degrades_with_reasons(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "_graph_rows", lambda: ([], "hypothesis graph absent or empty"))
    monkeypatch.setattr(rp, "CANON", tmp_path / "no_canon.json")
    monkeypatch.setattr(rp, "FORECASTS", tmp_path / "no_forecast.jsonl")
    monkeypatch.setattr(rp, "REPORT", tmp_path / "RESEARCH_PNL.json")
    monkeypatch.setattr(rp, "MARGINAL", tmp_path / "research_marginal.json")
    doc = rp.run()
    assert set(doc["gaps"]) == {"hypothesis_graph", "canon", "allocator_book"}
    assert doc["sources"] == {} and doc["unattributed_growth_per_day"] == 0.0
    assert all(v == rp.WORTH_FLOOR for v in doc["worth_by_arm"].values())
    assert (tmp_path / "RESEARCH_PNL.json").exists()
    assert (tmp_path / "research_marginal.json").exists()


def test_cert_source_reads_provenance_before_hunt_and_aliases_external():
    assert rp.cert_source({"hunt": "external_discoveries"}) == "external"
    assert rp.cert_source({"source": "plumbing_miner", "hunt": "external_discoveries"}) == \
        "plumbing_miner"
    assert rp.cert_source({"shadow_spec": {"hunt": "hunt16.json"}}) == "hunt16.json"
    assert rp.cert_source({}) == rp.UNKNOWN
    names = rp._sleeve_names({"sym": "XAUUSD", "shadow_spec": {
        "symbol": "XAUUSD", "family": "session_range_breakout", "selector": "asia"}})
    assert names == {"XAUUSD_session_range_breakout_asia", "XAUUSD_asia", "gold_asia"}


# --------------------------------------------------------------------------- governance
def test_sizing_and_exit_modules_carry_the_governance_rules_verbatim():
    """Word for word; only the docstring's line wrapping is folded, since the second rule is
    longer than the 100-column line the linter allows."""
    for mod in (ea, ac):
        doc = " ".join(mod.__doc__.split())
        assert RULE_1 in doc and RULE_2 in doc, mod.__name__
    assert "MEASURES ONLY" in ac.__doc__ and "NEVER CHANGES A CERTIFIED ENTRY" in ea.__doc__


def test_the_feedback_engines_never_name_a_crypto_exchange():
    for mod in (ea, ac, rp):
        src = Path(mod.__file__).read_text("utf-8").lower()
        for banned in ("binance", "bybit", "okx", "hyperliquid", "funding rate", "funding_rate",
                       "perp"):
            assert banned not in src, (mod.__name__, banned)
