"""The analyst panel: registered grammar only, a bear that removes nothing, and no seat -> inert."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import analyst_panel as ap  # noqa: E402


def _bars(n: int = 8_000, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2021-01-01", periods=n, freq="h", tz="UTC")
    close = 1.1 * np.exp(np.cumsum(rng.standard_t(4, n) * 0.001))
    open_ = np.concatenate(([close[0]], close[:-1]))
    wick = np.abs(rng.normal(0, 0.0005, n)) * close
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) + wick,
                         "low": np.minimum(open_, close) - wick, "close": close,
                         "tick_volume": rng.integers(50, 500, n)}, index=idx)


def test_catalogue_is_price_only_and_excludes_generic():
    cat = ap.catalogue()
    assert "generic" not in cat and "dual_thrust" in cat and "ffd_reversion" in cat
    assert "fade" in cat["dual_thrust"]["choices"]["mode"]


def test_valid_cell_refuses_off_grammar_and_keeps_unexpressed():
    v = ap._valid_cell(ap.catalogue())
    ok = {"family": "dual_thrust", "params": {"k1": 0.7, "mode": "fade"},
          "mechanism": "retail breakout chasing reverses", "falsifier": "no reversal after 2h"}
    assert v(ok) is None
    assert "not a registered" in v({**ok, "family": "rocket_science"})
    assert "no parameter" in v({**ok, "params": {"leverage": 3}})
    assert "outside" in v({**ok, "params": {"k1": 50.0}})
    assert "must be one of" in v({**ok, "params": {"mode": "yolo"}})
    assert "falsifier" in v({**ok, "falsifier": ""})
    assert v({**ok, "family": "NONE"}) is None


def _fake_ask(calls: list):
    def ask(organ, kind, *, task="", grammar="", context=(), n=3, validate=None, **_):
        calls.append(task)
        assert organ == ap.ORGAN and kind == "candidates"
        if task.startswith("You are the bear"):
            items = [{"idx": 0, "failure_class": "COST_DEATH",
                      "attack": "the breakout pays less than the spread on crosses",
                      "kill_test": "net-of-cost screen"}]
        else:
            items = [{"family": "dual_thrust", "params": {"k1": 0.4 + 0.1 * len(calls)},
                      "mechanism": "range breakout persistence in this session",
                      "falsifier": "breakouts revert within the day"},
                     {"family": "NONE", "mechanism": "order-book imbalance at the fix",
                      "falsifier": "no imbalance effect"}]
        items = [i for i in items if validate is None or validate(i) is None]
        return SimpleNamespace(verdict="RAN", items=items, trials_charged=float(len(items)),
                               discarded=0, reasons=[], why="")
    return ask


def test_pass_proposes_attacks_screens_and_donates(monkeypatch, tmp_path):
    from research import proposer_common as pc
    d = _bars()
    monkeypatch.setattr(ap, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(ap, "symbols", lambda: ["EURUSD"])
    monkeypatch.setattr(pc, "universe_meta", lambda: {"EURUSD": {}})
    monkeypatch.setattr(pc, "bars", lambda s: d)
    monkeypatch.setattr(pc, "cost_frac", lambda *a: 1e-5)
    monkeypatch.setattr(pc, "screen", lambda d, sigs, cost: {
        "t_gross": 2.1, "n_independent": 40, "clears_cost": True})
    got: dict = {}

    def _donate(source, rows, tests_run):
        got["rows"] = rows
        return tmp_path / "donated.json"
    monkeypatch.setattr(pc, "donate", _donate)
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": len(got.get("rows", []))})
    calls: list = []
    rep = ap.run(ask=_fake_ask(calls))
    assert rep["status"] == "OK" and rep["calls"] == 5          # four analysts + the bear
    assert rep["donation"]["status"] == "DONATED"
    rows = got["rows"]
    assert len(rows) == 4 and {r["family"] for r in rows} == {"dual_thrust"}
    assert all(r["evidence"]["hindsight_prior"] for r in rows)
    assert rows[0]["evidence"]["red_team"][0]["failure_class"] == "COST_DEATH"
    assert all(r["source_culture"] == "GLOBAL/llm" for r in rows)
    assert rep["unexpressed_total"] == 4
    # the same cells are not donated twice
    got.clear()
    assert ap.run(ask=_fake_ask([]))["candidates_this_pass"] == 0


def test_dark_seat_is_unmeasured_and_inert(monkeypatch, tmp_path):
    from research import proposer_common as pc
    monkeypatch.setattr(ap, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(ap, "symbols", lambda: ["EURUSD"])
    monkeypatch.setattr(pc, "universe_meta", lambda: {"EURUSD": {}})
    monkeypatch.setattr(pc, "bars", lambda s: _bars())

    def dark(*a, **k):
        return SimpleNamespace(verdict="UNMEASURED", items=[], trials_charged=0.0, discarded=0,
                               reasons=[], why="no panel")
    rep = ap.run(ask=dark)
    assert rep["status"] == "UNMEASURED" and rep["calls"] == 1 and rep["cells_proposed"] == 0


def test_leg_is_wired():
    from libs.research import proposer_seat as ps
    from libs.research.layers import LEG_LAYER
    text = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("analyst_panel"' in text
    assert LEG_LAYER["analyst_panel"] == "prediction"
    assert "analyst_panel" in ps.ORGANS
