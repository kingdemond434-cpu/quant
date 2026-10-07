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


def _wire(monkeypatch, tmp_path, sym: str, d, got: dict, when: list[str]) -> None:
    from research import proposer_common as pc
    monkeypatch.setattr(ap, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(ap, "TRIALS", tmp_path / "trials.jsonl")
    monkeypatch.setattr(ap, "_now", lambda: when[0])
    monkeypatch.setattr(ap, "symbols", lambda: [sym])
    monkeypatch.setattr(pc, "universe_meta", lambda: {sym: {}})
    monkeypatch.setattr(pc, "bars", lambda s: d)
    monkeypatch.setattr(pc, "cost_frac", lambda *a: 1e-5)

    def _screen(d, sigs, cost):
        got.setdefault("screened", []).append([s.time for s in sigs])
        return {"t_gross": 2.1, "n_independent": 40, "clears_cost": True}
    monkeypatch.setattr(pc, "screen", _screen)

    def _donate(source, rows, tests_run):
        got["rows"], got["tests_run"] = rows, tests_run
        return tmp_path / "donated.json"
    monkeypatch.setattr(pc, "donate", _donate)
    monkeypatch.setattr(pc, "donation_counts", lambda: {"donated": len(got.get("rows", []))})


def _trials(tmp_path) -> list[dict]:
    import json
    return [json.loads(x) for x in (tmp_path / "trials.jsonl").read_text().splitlines()]


def test_a_proposal_waits_for_post_proposal_evidence_then_donates_on_it(monkeypatch, tmp_path):
    import pandas as pd
    d = _bars()
    got: dict = {}
    when = ["2021-05-01T00:00:00+00:00"]
    _wire(monkeypatch, tmp_path, "EURUSD", d, got, when)
    calls: list = []
    rep = ap.run(ask=_fake_ask(calls))
    # proposed, attacked, screened in-sample -- and NOT donated: the model has read this sample
    assert rep["status"] == "OK" and rep["calls"] == 5          # four analysts + the bear
    assert rep["donation"]["status"] == "NOTHING_NEW" and "rows" not in got
    assert rep["forward_clock"]["queued_this_pass"] == 4
    assert rep["screen_tails"]["contaminated_by_hindsight"] is True
    first = _trials(tmp_path)[-1]
    assert first["ideas_proposed"] == 8                                   # 4 cells + 4 NONE
    assert first["falsifier_attacks"] == 1 and first["tests_run"] == 9    # + the bear's attack
    assert first["by_family"]["analyst_panel/falsifier_attacks"] == 1
    assert first["by_family"]["analyst_panel/unexpressed"] == 4
    # thirty days on: still under FORWARD_DAYS, still UNMEASURED, still not donated
    when[0] = "2021-05-31T00:00:00+00:00"
    rep = ap.run(ask=_fake_ask([]))
    assert "rows" not in got and rep["forward_clock"]["under_forward_days"] == 4
    # ninety days on: screened on the signals AFTER proposed_at only, then donated
    when[0] = "2021-07-30T00:00:00+00:00"
    got.pop("screened", None)
    rep = ap.run(ask=_fake_ask([]))
    rows = got["rows"]
    assert len(rows) == 4 and {r["family"] for r in rows} == {"dual_thrust"}
    since = pd.Timestamp("2021-05-01", tz="UTC")
    fwd = [t for t in got["screened"] if t and min(t) > since]
    assert len(fwd) >= 4
    ev = rows[0]["evidence"]
    assert ev["hindsight_prior"]
    assert ev["clean_from"] == ev["proposed_at"] == "2021-05-01T00:00:00+00:00"
    assert ev["forward_days"] >= ap.FORWARD_DAYS
    assert any(a["failure_class"] == "COST_DEATH" for r in rows for a in r["evidence"]["red_team"])
    assert all(r["source_culture"] == "GLOBAL/llm" for r in rows)
    # the donating pass is charged once, on the discovery file
    last = _trials(tmp_path)[-1]
    assert last["tests_run"] == 0 and got["tests_run"] == last["trials_total"] >= 4
    # the same cells are not donated twice
    got.clear()
    when[0] = "2021-08-30T00:00:00+00:00"
    assert ap.run(ask=_fake_ask([]))["candidates_this_pass"] == 0


def test_a_matured_cell_that_does_not_clear_is_retired(monkeypatch, tmp_path):
    from research import proposer_common as pc
    got: dict = {}
    when = ["2021-05-01T00:00:00+00:00"]
    _wire(monkeypatch, tmp_path, "EURUSD", _bars(), got, when)
    ap.run(ask=_fake_ask([]))
    monkeypatch.setattr(pc, "screen", lambda d, sigs, cost: {
        "t_gross": -0.4, "n_independent": 40, "clears_cost": False})
    when[0] = "2021-08-01T00:00:00+00:00"
    rep = ap.run(ask=_fake_ask([]))
    assert "rows" not in got and rep["forward_clock"]["failed_forward"] == 4
    assert rep["forward_clock"]["pending"] == 0 and rep["forward_clock"]["retired_total"] == 4


def test_dark_seat_is_unmeasured_and_its_pass_is_still_recorded(monkeypatch, tmp_path):
    got: dict = {}
    _wire(monkeypatch, tmp_path, "EURUSD", _bars(), got, ["2021-05-01T00:00:00+00:00"])

    def dark(*a, **k):
        return SimpleNamespace(verdict="UNMEASURED", items=[], trials_charged=0.0, discarded=0,
                               reasons=[], why="no reply: every model cooling down")
    rep = ap.run(ask=dark)
    assert rep["status"] == "UNMEASURED" and rep["calls"] == 1 and rep["cells_proposed"] == 0
    assert "no reply" in rep["why"]
    row = _trials(tmp_path)[-1]
    assert row["asks"] == 1 and row["tests_run"] == 0


def test_the_call_budget_stops_the_pass(monkeypatch, tmp_path):
    got: dict = {}
    _wire(monkeypatch, tmp_path, "EURUSD", _bars(), got, ["2021-05-01T00:00:00+00:00"])
    calls: list = []
    rep = ap.run(ask=_fake_ask(calls), calls=2)
    assert rep["calls"] == 2 and len(calls) == 2


def test_the_ledger_joins_the_panel_once(monkeypatch, tmp_path):
    import json

    from libs.research import experiment_ledger as el
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in (
        {"tests_run": 5, "by_family": {"dual_thrust": 3, "analyst_panel/unexpressed": 2}},
        {"tests_run": 0, "by_family": {}, "charged_on": "x.json"},
        {"tests_run": 9, "dry_run": True}, "not json")) + "\n")
    assert el._side_ledger(p) == (5, {"dual_thrust": 3, "analyst_panel/unexpressed": 2})


def test_compiler_keeps_the_hindsight_stamp():
    from research import miner_candidate_compiler as mcc
    row = {"evidence": {"proposed_at": "2021-05-01", "clean_from": "2021-05-01",
                        "hindsight_prior": True,
                        "red_team": [{"failure_class": "COST_DEATH"}]}}
    c = mcc._candidate("EURUSD", "dual_thrust", {"k1": 0.5}, "analyst_panel", row, "m")
    assert c["clean_from"] == "2021-05-01" and c["hindsight_prior"] is True
    assert c["red_team"][0]["failure_class"] == "COST_DEATH"
    assert "clean_from" not in mcc._candidate("EURUSD", "dual_thrust", {}, "x", {}, "m")


def test_leg_is_wired():
    from libs.research import proposer_seat as ps
    from libs.research.layers import LEG_LAYER
    text = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("analyst_panel"' in text
    assert LEG_LAYER["analyst_panel"] == "prediction"
    assert "analyst_panel" in ps.ORGANS


def test_china_lens_only_on_cn_analogues_and_carries_cn_culture(monkeypatch, tmp_path):
    got: dict = {}
    when = ["2021-05-01T00:00:00+00:00"]
    _wire(monkeypatch, tmp_path, "USDCNH", _bars(), got, when)
    calls: list = []
    rep = ap.run(ask=_fake_ask(calls))
    assert rep["calls"] == 6 and any(t.startswith("您是") for t in calls)
    when[0] = "2021-08-01T00:00:00+00:00"
    ap.run(ask=_fake_ask([]))
    cn = [r for r in got["rows"] if r["evidence"]["analyst"] == "china_market_analyst"]
    assert cn and all(r["source_culture"] == "CN/zh" for r in cn)
    assert not ap.LENS_ONLY["china_market_analyst"]("EURUSD")
