"""Every look is charged once, by identity, whether or not the pass donates (audit PR166_v2)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import proposer_common as pc  # noqa: E402


def _null_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text("utf-8").splitlines() if ln.strip()]


def _bars(n: int = 9_000) -> pd.DataFrame:
    rng = np.random.default_rng(4)
    idx = pd.date_range("2019-01-01", periods=n, freq="h", tz="UTC")
    close = 1.3 * np.exp(np.cumsum(rng.standard_t(4, n) * 0.001))
    open_ = np.concatenate(([close[0]], close[:-1]))
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) * 1.0005,
                         "low": np.minimum(open_, close) * 0.9995, "close": close}, index=idx)


def test_donate_or_charge_lands_the_looks_in_exactly_one_place(monkeypatch, tmp_path):
    monkeypatch.setattr(pc, "NULL_TRIALS", tmp_path / "null.jsonl")
    monkeypatch.setattr(pc, "donate", lambda s, rows, n: tmp_path / "d.json" if rows else None)
    got = pc.donate_or_charge("x", [{"a": 1}], 7, {"f": 7})
    assert got["charged_on"] == "discovery_file" and not _null_rows(tmp_path / "null.jsonl")
    got = pc.donate_or_charge("x", [], 5, {"f": 5})
    assert got["charged_on"] == "null_pass_trials"
    assert [r["tests_run"] for r in _null_rows(tmp_path / "null.jsonl")] == [5]
    assert pc.donate_or_charge("x", [], 0)["charged_on"] is None      # no new look, no row


def test_elitequant_charges_a_null_pass_and_never_the_same_cell_twice(monkeypatch, tmp_path):
    from research import elitequant_breadth as eb

    d = _bars()
    monkeypatch.setattr(pc, "NULL_TRIALS", tmp_path / "null.jsonl")
    monkeypatch.setattr(eb, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(eb, "symbols", lambda: ["EURUSD"])
    monkeypatch.setattr(eb, "FAMILIES", {"dual_thrust": eb.FAMILIES["dual_thrust"]})
    monkeypatch.setattr(pc, "universe_meta", lambda: {"EURUSD": {}})
    monkeypatch.setattr(pc, "bars", lambda s: d)
    monkeypatch.setattr(pc, "cost_frac", lambda *a: 1e-5)
    monkeypatch.setattr(pc, "screen", lambda d, sigs, cost: {
        "t_gross": 0.1, "n_independent": len(sigs), "clears_cost": False})
    rep = eb.seed(budget_s=120)
    n_cells = len(eb.grid("dual_thrust"))
    assert rep["new_looks_charged"] == n_cells and rep["candidates_this_pass"] == 0
    assert [r["tests_run"] for r in _null_rows(tmp_path / "null.jsonl")] == [n_cells]
    # tomorrow's re-screen of the same identities is not a new trial
    state = json.loads((tmp_path / "state.json").read_text("utf-8"))
    for c in state["cells"].values():
        c["day"] = "2000-01-01"
    (tmp_path / "state.json").write_text(json.dumps(state), "utf-8")
    assert eb.seed(budget_s=120)["new_looks_charged"] == 0
    assert len(_null_rows(tmp_path / "null.jsonl")) == 1


def test_zoo_charges_each_book_once_and_a_null_pass_too(monkeypatch, tmp_path):
    from research import zoo_breadth as zb

    monkeypatch.setattr(pc, "NULL_TRIALS", tmp_path / "null.jsonl")
    monkeypatch.setattr(zb, "STATE", tmp_path / "zoo_state.json")
    members = [f"S{i}" for i in range(12)]
    monkeypatch.setattr(zb, "classes", lambda: {"fx": members})
    monkeypatch.setattr(zb.zoo, "class_panel", lambda sym: ({"panel": True},))
    monkeypatch.setattr(zb.zoo, "catalogue", lambda: {"a1": {"zoo": "alpha101"},
                                                       "a2": {"zoo": "alpha101"}})
    monkeypatch.setattr(zb.zoo, "compute", lambda aid, panel: "score")
    monkeypatch.setattr(zb, "book_ic", lambda score, panel, h: (0.1, 300))   # never survives
    rep = zb.seed(budget_s=60)
    books = 2 * len(zb.HORIZONS)
    assert rep["new_looks_charged"] == 2 * books                       # both signs per book
    assert [r["tests_run"] for r in _null_rows(tmp_path / "null.jsonl")] == [2 * books]
    state = json.loads((tmp_path / "zoo_state.json").read_text("utf-8"))
    for b in state["books"].values():
        b["day"] = "2000-01-01"
    (tmp_path / "zoo_state.json").write_text(json.dumps(state), "utf-8")
    assert zb.seed(budget_s=60)["new_looks_charged"] == 0
