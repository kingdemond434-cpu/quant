"""The elitequant leg: one trial per entry behaviour, a per-cell budget, the report written first."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk.engine import Signal  # noqa: E402
from research import elitequant_breadth as eb  # noqa: E402
from research import proposer_common as pc  # noqa: E402


def _bars(n: int = 6000) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    idx = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC").as_unit("ns")
    c = 1.2 * np.exp(np.cumsum(rng.normal(0, 0.001, n)))
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.0005,
                         "low": np.minimum(o, c) * 0.9995, "close": c}, index=idx)


def _entries(d: pd.DataFrame, *, hold: int = 5, sleep: float = 0.0) -> list[Signal]:
    time.sleep(sleep)
    return [Signal(time=d.index[i], side=1, stop=float(d["close"].iloc[i]) * 0.99,
                   target=float(d["close"].iloc[i]) * 1.02, ttl_bars=hold, tag="x")
            for i in range(100, len(d) - 10, 200)]


def _world(monkeypatch, tmp_path, families, grid):
    d = _bars()
    monkeypatch.setattr(eb, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(eb, "OUT", tmp_path / "ELITEQUANT_BREADTH.json")
    monkeypatch.setattr(eb, "FAMILIES", families)
    monkeypatch.setattr(eb, "PARAM_GRID", grid)
    monkeypatch.setattr(eb, "CULTURE", dict.fromkeys(families, {}))
    monkeypatch.setattr(eb, "HISTORY_GATED", {})
    monkeypatch.setattr(eb, "CLASS_ONLY", {})
    monkeypatch.setattr(eb, "PAIR_OF", {})
    monkeypatch.setattr(eb, "SYMBOL_KEYED", frozenset())
    monkeypatch.setattr(eb, "symbols", lambda: ["EURUSD", "GBPUSD"])
    monkeypatch.setattr(pc, "universe_meta", lambda: {})
    monkeypatch.setattr(pc, "bars", lambda s: d)
    monkeypatch.setattr(pc, "cost_frac", lambda *a: 1e-5)
    monkeypatch.setattr(pc, "screen", lambda d, sigs, cost: {
        "t_gross": 0.1, "n_independent": len(sigs), "clears_cost": False})
    charged: list = []
    monkeypatch.setattr(pc, "donate_or_charge",
                        lambda src, rows, n, by: charged.append((n, by)) or
                        {"path": None, "charged_on": "null"})
    return charged


def test_two_holding_windows_with_one_set_of_entries_are_one_trial(monkeypatch, tmp_path):
    charged = _world(monkeypatch, tmp_path, {"f": _entries}, {"f": {"hold": [5, 20]}})
    rep = eb.seed(budget_s=60)
    assert charged[0][0] == 2                    # one per symbol, not one per params
    assert rep["cells_by_family"]["f"]["same_behaviour_not_recharged"] == 2
    # the behaviour ledger persists, so a later pass never recharges it
    assert len(json.loads((tmp_path / "state.json").read_text())["charged_behaviours"]) == 2


def test_the_budget_is_checked_per_cell(monkeypatch, tmp_path):
    slow = {f"s{i}": (lambda d, **k: _entries(d, sleep=0.3)) for i in range(8)}
    _world(monkeypatch, tmp_path, slow, {})
    t0 = time.monotonic()
    rep = eb.seed(budget_s=0.5)
    assert time.monotonic() - t0 < 2.0           # stops mid-symbol, never runs all 16 cells
    assert rep["stopped_because"].startswith("time budget")


def test_report_lands_before_the_add_ons(monkeypatch, tmp_path):
    _world(monkeypatch, tmp_path, {"f": _entries}, {})
    from research import cross_excitation, total_expectation
    seen = {}

    def ce_run(budget_s):
        seen["report_at_addon"] = json.loads((tmp_path / "ELITEQUANT_BREADTH.json").read_text())
        raise RuntimeError("add-on overran")
    monkeypatch.setattr(cross_excitation, "run", ce_run)
    monkeypatch.setattr(total_expectation, "run",
                        lambda budget_s: {"status": "RAN", "ran": []})
    assert eb.main(["--once", "--budget-s", "780"]) == 0
    assert seen["report_at_addon"]["status"] == "OK"
    assert seen["report_at_addon"]["seed_budget_s"] == 780 - eb.ADDON_BUDGET_S == 600
    final = json.loads((tmp_path / "ELITEQUANT_BREADTH.json").read_text())
    assert final["cross_excitation"]["status"] == "UNMEASURED"
