"""Research the researcher: method challengers, the reusable holdout and the frontier report."""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for p in (str(ROOT), str(DESK), str(DESK / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from test_monitor_proposers import _bars  # noqa: E402

from libs.data.feature_store import FeatureStore  # noqa: E402
from libs.research import coevolution as C  # noqa: E402
from libs.research import reusable_holdout as rh  # noqa: E402
from research import factor_model_coevolution as fmc  # noqa: E402
from research import meta_rnd  # noqa: E402


def test_the_sequential_baseline_spends_no_more_than_the_joint_search(tmp_path):
    d = _bars(days=120, seed=4)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        s = C.sequential(d, store=FeatureStore(tmp_path / "fs"), n_evals=9,
                         models=("logistic", "hist_gb"))
    assert 0 < s["pairings_evaluated"] <= 9
    assert s["reference_model"] == "logistic" and s["best"] is not None


def test_head_to_head_selects_on_the_dev_bars_and_scores_once_on_the_untouched_tail(tmp_path):
    d = _bars(days=250, seed=5)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = C.head_to_head(d, store=FeatureStore(tmp_path / "fs"), budget_s=30,
                           models=("logistic", "hist_gb"))
    assert r["bars_dev"] + r["bars_test"] == len(d)
    assert r["evals"]["sequential"] <= r["evals"]["joint"]          # matched compute
    assert r["joint"]["net_gain"] is not None and r["sequential"]["net_gain"] is not None
    assert r["winner"] in ("joint", "sequential", "tie")
    assert r["trials"] == r["evals"]["joint"] + r["evals"]["sequential"]


def test_evaluate_from_row_scores_only_the_tail():
    class Store:
        def matrix(self, df, specs):
            import numpy as np
            return np.ones((len(df), 1))
    seen = {}

    def fake_compete(x, y, models):
        seen["n"] = len(y)
        return {"results": {models[0]: {"n": len(y)}}}
    import numpy as np
    import pandas as pd
    df = pd.DataFrame({"close": np.linspace(1, 2, 120)})
    orig = C.compete
    C.compete = fake_compete
    try:
        C.evaluate(df, [0], "logistic", Store(), 1, None, C.VOCAB, from_row=100)
    finally:
        C.compete = orig
    assert seen["n"] <= 20


def test_the_method_challenger_records_every_run_and_lets_the_arena_judge(tmp_path,
                                                                        monkeypatch):
    monkeypatch.setattr(fmc, "H2H", tmp_path / "h2h.jsonl")
    monkeypatch.setattr(fmc, "_symbols", lambda s: (["SYNA"], {}))
    monkeypatch.setattr(fmc, "healthy_zoo_models", lambda m: (("logistic",), {}))
    monkeypatch.setattr(fmc.pc, "bars", lambda s: _bars(days=200, seed=1))
    outcomes = iter(["sequential"] * 6 + ["joint"])

    def fake_h2h(df, **kw):
        w = next(outcomes)
        return {"winner": w, "trials": 10,
                "joint": {"net_gain": 0.001 if w == "joint" else -0.002},
                "sequential": {"net_gain": -0.001 if w == "joint" else 0.0}}
    monkeypatch.setattr(C, "head_to_head", fake_h2h)
    for _ in range(7):
        ch = fmc.challenger()
    assert ch["runs"] == 7 and ch["wins"] == {"joint": 1, "sequential": 6}
    assert ch["trials"] == 10 and ch["applied"] is False
    assert ch["oos_net_gain_gap_joint_minus_sequential"]["n"] == 7
    assert set(ch["verdict"]["arms"]) == {"joint", "sequential"}


def test_thresholdout_answers_from_train_until_the_holdout_disagrees(tmp_path):
    state = tmp_path / "rh.json"
    agree = rh.thresholdout("s", {"a": (1.0, 1.0)}, scale=1.0, seed=1, state_path=state)
    assert agree["answers"]["a"] == 1.0 and agree["overfit"] == []
    off = rh.thresholdout("s", {"b": (1.0, 3.0)}, scale=1.0, seed=2, state_path=state)
    assert off["overfit"] == ["b"] and abs(off["answers"]["b"] - 3.0) < 0.5
    assert off["budget_left"] == rh.BUDGET - 1


def test_the_holdout_budget_is_charged_across_passes_and_exhausts(tmp_path):
    state = tmp_path / "rh.json"
    for i in range(3):
        out = rh.thresholdout("s", {"x": (0.0, 10.0)}, scale=1.0, budget=2, seed=i,
                              state_path=state)
    assert out["status"] == "EXHAUSTED" and out["answers"]["x"] is None
    assert json.loads(state.read_text())["s"]["questions"] == 3


def test_a_row_never_changes_sides():
    assert {rh.split(f"c{i}") for i in range(50)} == {"train", "holdout"}
    assert all(rh.split("c7") == rh.split("c7") for _ in range(5))


def _rows(n):
    return [{"cert_id": f"c{i}", "results": {
        "cost_surface": {"seconds": 1.0, "verdict": "FAIL" if i % 3 == 0 else "PASS"},
        "placebo": {"seconds": 2.0, "verdict": "FAIL" if i % 2 == 0 else "PASS"}}}
        for i in range(n)]


def test_meta_rnds_pick_goes_through_the_reusable_holdout(tmp_path):
    g = meta_rnd.guarded_winner(_rows(60), {}, state_path=tmp_path / "rh.json")
    assert g["status"] in ("VALID", "EXHAUSTED") and g["winner"] in meta_rnd.POLICIES
    assert g["n_train"] + g["n_holdout"] == 60
    small = meta_rnd.guarded_winner(_rows(4), {}, state_path=tmp_path / "rh.json")
    assert small["status"] == "UNMEASURED" and small["winner"] is None


def test_the_frontier_report_names_every_limitation_and_never_passes_an_absence(tmp_path,
                                                                              monkeypatch):
    monkeypatch.setattr(meta_rnd, "DESK", tmp_path)
    fr = meta_rnd.frontier({"ordering": {}})
    ids = [r["id"] for r in fr["limitations"]]
    assert len(ids) == len(set(ids)) == 9
    for r in fr["limitations"]:
        assert r["status"] in ("NOT_BUILT", "UNMEASURED", "BLOCKED_BY_POLICY")
        assert r["next_experiment"] and r["resources_to_go_further"] and r["limit"]
        assert all(a["state"] == "ABSENT" for a in r["artifacts"].values())
    assert fr["measured_share"] == 0.0


def test_the_frontier_reads_the_method_challenger_when_it_has_run(tmp_path, monkeypatch):
    monkeypatch.setattr(meta_rnd, "DESK", tmp_path)
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "COEVOLUTION.json").write_text(json.dumps({"method_challenger": {
        "decided": 8, "runs": 8, "wins": {"joint": 2, "sequential": 6},
        "oos_net_gain_gap_joint_minus_sequential": {"mean": -0.001, "se": 0.0004, "n": 8},
        "verdict": {"arms": {"joint": {"verdict": "TRAILS"}, "sequential": {"verdict": "LEADS"}}}
    }}))
    fr = meta_rnd.frontier({"ordering": {"reusable_holdout": {"status": "VALID",
                                                              "budget_left": 60}}})
    rows = {r["id"]: r for r in fr["limitations"]}
    assert rows["joint_feature_model_search"]["status"] == "MEASURED"
    assert rows["joint_feature_model_search"]["result"]["verdicts"]["joint"] == "TRAILS"
    assert rows["adaptive_holdout_reuse"]["status"] == "MEASURED"


@pytest.mark.parametrize("name", ["RESEARCH_FRONTIER.json"])
def test_the_frontier_has_a_home_on_the_hourly_meta_rnd_leg(name):
    assert meta_rnd.FRONTIER.name == name
    src = (DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '"meta_rnd", "research/meta_rnd.py", "--once"' in src
