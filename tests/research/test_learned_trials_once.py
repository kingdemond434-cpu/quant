"""The learned miners charge each trial once, ever, and give every panel its own budget.

Audit of #352 (2026-10-13): the daily pass re-appended the same trial ids every day and the
lifetime ledger counted raw rows, so the judge's deflation N grew by the whole grid daily for
trials already charged; and the retail panel, queued behind the core panel's grid, never ran.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
_DESK = _ROOT / "desks" / "mt5"
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import trial_ledger as TL  # noqa: E402


def _fake_bars(symbols) -> dict[str, pd.DataFrame]:
    idx = pd.date_range("2024-01-01", periods=48, freq="h", tz="UTC")
    return {s: pd.DataFrame({"close": np.linspace(1.0, 1.1, 48)}, index=idx) for s in symbols}


def _fake_mine(calls: list):
    def fake(model, bars, meta, *, deadline, panel_name="core", **_k):
        calls.append((model, panel_name, deadline))
        trials = [TL.Trial(trial_id=f"{panel_name}:{s}:{model}:z1.0",
                           family=f"learned_{model}:{model}_fam",
                           descriptors={"symbol": s}, params={})
                  for s in sorted(bars)]
        return {"source": f"learned_{model}", "configs": {}, "proposals": [], "rows": [],
                "_trials": trials, "tests_attempted": len(trials), "effective_trials": 1.0,
                "panel": sorted(bars)}
    return fake


def _run(LM, tmp_path: Path, calls: list, budget_s: float = 100.0,
         ledger: Path | None = None) -> dict:
    orig_mine, orig_load = LM.mine, LM.load_bars
    try:
        LM.mine = _fake_mine(calls)
        LM.load_bars = lambda symbols=LM.PANEL, base=None: _fake_bars(symbols)
        return LM.run(budget_s=budget_s, models=("gnn", "rocket"), donate=False,
                      report=tmp_path / "r.json", trials_path=ledger or tmp_path / "t.jsonl",
                      publish_axes=False, contract=False)
    finally:
        LM.mine, LM.load_bars = orig_mine, orig_load


def test_two_daily_runs_charge_each_trial_once(tmp_path: Path, monkeypatch) -> None:
    import learned_miners as LM

    from libs.research import experiment_ledger as EL
    desk = tmp_path / "desks" / "mt5"
    (desk / "data").mkdir(parents=True)
    monkeypatch.setattr(EL, "DESK", desk)
    ledger = desk / "data" / "learned_miners_trials.jsonl"
    calls: list = []
    r1 = _run(LM, tmp_path, calls, ledger=ledger)
    n1 = len(ledger.read_text("utf-8").splitlines())
    c1, _f1 = EL._proposer_counts()
    r2 = _run(LM, tmp_path, calls, ledger=ledger)
    n2 = len(ledger.read_text("utf-8").splitlines())
    c2, _f2 = EL._proposer_counts()
    expected = 2 * (len(LM.PANEL) + len(LM.RETAIL_PANEL))
    assert n1 == n2 == c1 == c2 == expected
    assert sum(m["tests_new"] for m in r1["miners"].values()) == expected
    assert sum(m["tests_new"] for m in r2["miners"].values()) == 0


def test_repeated_daily_discovery_files_are_one_charge(tmp_path: Path, monkeypatch) -> None:
    from libs.research import experiment_ledger as EL
    desk = tmp_path / "desks" / "mt5"
    seat = desk / "data" / "intelligence" / "learned_gnn"
    seat.mkdir(parents=True)
    for day in ("20261011_0300", "20261012_0300", "20261013_0300"):
        (seat / f"discoveries_{day}.json").write_text(json.dumps(
            {"tests_run": 384, "discoveries": [{"family": "gnn_propagation"}]}), "utf-8")
    monkeypatch.setattr(EL, "DESK", desk)
    total, by_fam = EL._proposer_counts()
    assert total == 384 and by_fam == {"gnn_propagation": 384}
    # With the ledger holding the same 384 distinct ids (re-appended on three days), still 384.
    rows = [{"trial_id": f"EURUSD:g{i}", "family": "learned_gnn:gnn_propagation",
             "donated": True} for i in range(384)] * 3
    (desk / "data" / "learned_miners_trials.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", "utf-8")
    total, by_fam = EL._proposer_counts()
    assert total == 384 and by_fam == {"gnn_propagation": 384}


def test_every_panel_gets_its_own_budget_slice(tmp_path: Path) -> None:
    import learned_miners as LM
    calls: list = []
    t0 = time.monotonic()
    _run(LM, tmp_path, calls, budget_s=100.0)
    core = [d for _m, p, d in calls if p == "core"]
    retail = [d for _m, p, d in calls if p == "retail_heavy"]
    assert core and retail
    assert max(core) - t0 < 55.0                    # the core panel stops at half the budget
    assert min(retail) - t0 > 95.0                  # the retail panel gets the rest


def test_a_config_past_its_deadline_is_never_started() -> None:
    import learned_miners as LM
    rng = np.random.default_rng(0)
    idx = pd.date_range("2020-01-01", periods=24 * 700, freq="h", tz="UTC")
    bars = {s: pd.DataFrame({"open": c, "high": c, "low": c, "close": c, "spread": 10.0},
                            index=idx)
            for s in LM.PANEL[:6] for c in [np.exp(np.cumsum(rng.normal(0, 1e-3, len(idx))))]}
    res = LM.mine("rocket", bars, {}, deadline=time.monotonic() - 1.0)
    assert res["tests_attempted"] == 0
    assert all(c["verdict"] == "UNMEASURED" for c in res["configs"].values())


def test_the_contract_is_refreshed_weekly(tmp_path: Path, monkeypatch) -> None:
    import learned_miners as LM
    p = tmp_path / "c.json"
    p.write_text("{}", "utf-8")
    assert LM._refresh_contract(p)["status"] == "FRESH"
    seen = {}

    def fake(out_path=None, cell_budget_s=None, **_k):
        seen["budget"] = cell_budget_s
        return {"miners": {"gnn": {"verdict": "NO_GAIN: x"}}}

    monkeypatch.setattr(LM, "measure_contract", fake)
    got = LM._refresh_contract(p, now=time.time() + LM.CONTRACT_EVERY_S + 1)
    assert got["status"] == "MEASURED" and got["verdicts"] == {"gnn": "NO_GAIN: x"}
    assert seen["budget"] == LM.CONTRACT_CELL_BUDGET_S
