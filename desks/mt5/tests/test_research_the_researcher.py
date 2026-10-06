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
                         models=("logistic", "ridge_sign"))
    assert s["pairings_evaluated"] == 9                  # equal, not at most
    assert s["reference_model"] == "logistic" and s["best"] is not None


def test_head_to_head_selects_on_the_dev_bars_and_scores_once_on_the_untouched_tail(tmp_path):
    d = _bars(days=250, seed=5)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = C.head_to_head(d, store=FeatureStore(tmp_path / "fs"), budget_s=30,
                           models=("logistic", "ridge_sign"))
    assert r["bars_dev"] + r["bars_test"] == len(d)
    assert r["matched_compute"] is (r["evals"]["sequential"] == r["evals"]["joint"])
    assert r["evals"]["sequential"] <= r["evals"]["joint"]
    assert r["joint"]["net_gain"] is not None and r["sequential"]["net_gain"] is not None
    assert r["winner"] in ("joint", "sequential", "tie")
    assert r["evals"]["tail_scorings"] == 2                     # both tail scorings are trials
    assert r["trials"] == r["evals"]["joint"] + r["evals"]["sequential"] + 2


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
    outcomes = iter(["sequential"] * 6 + ["joint", "unmatched", "boom"])

    def fake_h2h(df, progress=None, **kw):
        w = next(outcomes)
        if w == "boom":
            progress["spent_bound"] = 17
            raise RuntimeError("store unreadable")
        return {"winner": "joint" if w == "unmatched" else w, "trials": 10,
                "matched_compute": w != "unmatched",
                "joint": {"net_gain": 0.001 if w != "sequential" else -0.002},
                "sequential": {"net_gain": -0.001 if w != "sequential" else 0.0}}
    monkeypatch.setattr(C, "head_to_head", fake_h2h)
    for _ in range(9):
        ch = fmc.challenger()
    assert ch["runs"] == 9 and ch["wins"] == {"joint": 1, "sequential": 6}   # matched only
    assert ch["unmatched_runs"] == 1 and ch["failed_runs"] == 1
    assert ch["trials"] == 17 and ch["applied"] is False      # a failed run is still charged
    assert ch["oos_net_gain_gap_joint_minus_sequential"]["n"] == 7
    assert set(ch["verdict"]["arms"]) == {"joint", "sequential"}
    rows = [json.loads(x) for x in fmc.H2H.read_text().splitlines()]
    assert sum(int(r.get("trials") or 0) for r in rows) == 8 * 10 + 17


def _state(tmp_path):
    p = tmp_path / "rh.json"
    rh.init_state(p)
    return p


def test_thresholdout_answers_from_train_until_the_holdout_disagrees(tmp_path):
    state = _state(tmp_path)
    agree = rh.thresholdout("s", {"a": (1.0, 1.0)}, scale=1.0, seed=1, state_path=state)
    assert agree["answers"]["a"] == 1.0 and agree["overfit"] == []
    off = rh.thresholdout("s", {"b": (1.0, 3.0)}, scale=1.0, seed=2, state_path=state)
    assert off["overfit"] == ["b"] and abs(off["answers"]["b"] - 3.0) < 0.5
    assert off["budget_left"] == rh.BUDGET - 1


def test_the_holdout_budget_is_charged_across_passes_and_exhausts(tmp_path):
    state = _state(tmp_path)
    for i in range(3):
        out = rh.thresholdout("s", {"x": (0.0, 10.0)}, scale=1.0, budget=2, seed=i,
                              state_path=state)
    assert out["status"] == "EXHAUSTED" and out["answers"]["x"] is None
    assert json.loads(state.read_text())["s"]["questions"] == 3


@pytest.mark.parametrize("damage", ["garbage", "non_int", "not_a_dict"])
def test_a_damaged_budget_file_reads_exhausted_and_never_refills(tmp_path, damage):
    state = _state(tmp_path)
    rh.thresholdout("s", {"x": (0.0, 10.0)}, scale=1.0, budget=1, seed=0, state_path=state)
    if damage == "garbage":
        state.write_text("{not json")
    elif damage == "non_int":
        state.write_text(json.dumps({"s": {"budget_left": "64", "questions": 1}}))
    else:
        state.write_text(json.dumps(["s"]))
    out = rh.thresholdout("s", {"x": (0.0, 0.0)}, scale=1.0, seed=1, state_path=state)
    assert out["status"] == "EXHAUSTED" and out["answers"]["x"] is None and out["state_error"]


def test_restoring_or_deleting_the_state_never_refills_an_opened_study(tmp_path):
    state = _state(tmp_path)
    stub = state.read_text()
    rh.thresholdout("s", {"x": (0.0, 10.0)}, scale=1.0, budget=1, seed=0, state_path=state)
    state.write_text(stub)                                      # `git checkout` of the stub
    out = rh.thresholdout("s", {"x": (0.0, 0.0)}, scale=1.0, seed=1, state_path=state)
    assert out["status"] == "EXHAUSTED" and out["answers"]["x"] is None   # the register spent it
    state.unlink()                                              # deleted outright: same
    assert rh.thresholdout("s", {"x": (0.0, 0.0)}, scale=1.0, seed=2,
                           state_path=state)["status"] == "EXHAUSTED"
    # A study never opened still gets its budget, on a recreated state.
    assert rh.thresholdout("t", {"x": (1.0, 1.0)}, scale=1.0, seed=3,
                           state_path=state)["status"] == "VALID"


def test_an_older_state_snapshot_cannot_refill(tmp_path):
    state = _state(tmp_path)
    rh.thresholdout("s", {"a": (1.0, 1.0)}, scale=1.0, budget=2, seed=0, state_path=state)
    snapshot = state.read_text()                                # budget_left 2 in the state
    for i in range(2):
        rh.thresholdout("s", {"x": (0.0, 10.0)}, scale=1.0, budget=2, seed=i + 1,
                        state_path=state)
    state.write_text(snapshot)
    out = rh.thresholdout("s", {"x": (0.0, 10.0)}, scale=1.0, budget=2, seed=9,
                          state_path=state)
    assert out["status"] == "EXHAUSTED" and out["answers"]["x"] is None


def test_a_register_restored_to_its_stub_cannot_refill_what_the_state_holds(tmp_path):
    state = _state(tmp_path)
    stub = rh.register_path(state).read_text()
    rh.thresholdout("s", {"x": (0.0, 10.0)}, scale=1.0, budget=1, seed=0, state_path=state)
    rh.register_path(state).write_text(stub)
    out = rh.thresholdout("s", {"x": (0.0, 0.0)}, scale=1.0, budget=1, seed=1, state_path=state)
    assert out["status"] == "EXHAUSTED" and out["answers"]["x"] is None


def test_a_missing_register_answers_nothing(tmp_path):
    state = _state(tmp_path)
    rh.register_path(state).unlink()
    out = rh.thresholdout("s", {"x": (1.0, 1.0)}, scale=1.0, seed=0, state_path=state)
    assert out["status"] == "EXHAUSTED" and out["answers"]["x"] is None
    assert "missing or unreadable" in out["state_error"]
    assert rh.rotate("s", {"k"}, state) is None


def test_an_unwritable_register_answers_nothing(tmp_path, monkeypatch):
    state = _state(tmp_path)
    rh.thresholdout("s", {"a": (1.0, 1.0)}, scale=1.0, seed=0, state_path=state)

    def refuse(path, row):
        raise OSError("read-only")
    monkeypatch.setattr(rh, "_append", refuse)
    out = rh.thresholdout("s", {"x": (1.0, 1.0)}, scale=1.0, seed=1, state_path=state)
    assert out["status"] == "EXHAUSTED" and out["answers"]["x"] is None


def test_epochs_survive_a_restored_state_file(tmp_path):
    state = _state(tmp_path)
    stub = state.read_text()
    assert rh.rotate("b", {"k1", "k2"}, state) == "b@1"
    state.write_text(stub)
    assert rh.epoch("b", state) == ("b@1", {"k1", "k2"})


def test_an_unsaveable_charge_answers_nothing(tmp_path, monkeypatch):
    state = _state(tmp_path)

    def refuse(path, doc):
        raise OSError("read-only")
    monkeypatch.setattr(rh, "_save", refuse)
    out = rh.thresholdout("s", {"x": (1.0, 1.0)}, scale=1.0, seed=0, state_path=state)
    assert out["status"] == "EXHAUSTED" and out["answers"]["x"] is None


def test_unseeded_noise_differs_between_identical_questions(tmp_path):
    state = _state(tmp_path)
    got = {rh.thresholdout("s", {"x": (1.0, 3.0)}, scale=1.0, budget=50,
                           state_path=state)["answers"]["x"] for _ in range(5)}
    assert len(got) > 1


def test_an_exhausted_study_rotates_to_rows_it_never_saw(tmp_path):
    state = tmp_path / "rh.json"
    state.write_text(json.dumps({"meta_rnd.test_ordering@0": {"budget_left": 0,
                                                              "questions": 64}}))
    rh.init_state(state)                                         # register stub, state kept
    g = meta_rnd.guarded_winner(_rows(60), {}, state_path=state)
    assert g["status"] == "EXHAUSTED" and g["frozen"]
    assert g["rotated_to"] == "meta_rnd.test_ordering@1"
    stale = meta_rnd.guarded_winner(_rows(60), {}, state_path=state)
    assert stale["status"] == "UNMEASURED" and stale["rows_retired"] == 60
    fresh = [r | {"cert_id": "n" + r["cert_id"]} for r in _rows(60)]
    again = meta_rnd.guarded_winner(fresh, {}, state_path=state)
    assert again["study"] == "meta_rnd.test_ordering@1" and again["status"] == "VALID"


def test_a_row_never_changes_sides():
    assert {rh.split(f"c{i}") for i in range(50)} == {"train", "holdout"}
    assert all(rh.split("c7") == rh.split("c7") for _ in range(5))


def _rows(n):
    return [{"cert_id": f"c{i}", "results": {
        "cost_surface": {"seconds": 1.0, "verdict": "FAIL" if i % 3 == 0 else "PASS"},
        "placebo": {"seconds": 2.0, "verdict": "FAIL" if i % 2 == 0 else "PASS"}}}
        for i in range(n)]


def test_meta_rnds_pick_goes_through_the_reusable_holdout(tmp_path):
    g = meta_rnd.guarded_winner(_rows(60), {}, state_path=_state(tmp_path))
    assert g["status"] in ("VALID", "EXHAUSTED") and g["winner"] in meta_rnd.POLICIES
    assert g["n_train"] + g["n_holdout"] == 60
    small = meta_rnd.guarded_winner(_rows(4), {}, state_path=tmp_path / "rh.json")
    gone = tmp_path / "gone.json"                                # a state file lost after the
    rh.register_path(gone).write_text("\n".join(json.dumps(r) for r in (   # study was spent
        {"study": "meta_rnd.test_ordering@0", "budget": rh.BUDGET},
        {"charge": "meta_rnd.test_ordering@0", "spent": rh.BUDGET})) + "\n")
    lost = meta_rnd.guarded_winner(_rows(60), {}, state_path=gone)
    assert lost["status"] == "EXHAUSTED"
    nore = tmp_path / "noregister.json"                          # no register at all: closed,
    gn = meta_rnd.guarded_winner(_rows(60), {}, state_path=nore)  # and never rotated
    assert gn["status"] == "EXHAUSTED" and not gn.get("rotated_to")
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


def _daily(n_days: int, seed: int = 0) -> dict[str, dict[str, float]]:
    import numpy as np
    rng = np.random.default_rng(seed)
    days = [f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}" for i in range(n_days)]
    return {f"s{k}": {d: float(rng.normal(0.05 * (k - 1), 1.0)) for d in days}
            for k in range(4)}


def test_cadence_and_bound_reads_unmeasured_on_a_short_book():
    out = meta_rnd.cadence_and_bound(_daily(20))
    assert out["status"] == "UNMEASURED" and "need" in out["why"]


def test_cadence_and_bound_publishes_intervals_turnover_and_a_nonnegative_gap():
    out = meta_rnd.cadence_and_bound(_daily(150, seed=3), boots=40)
    assert out["status"] == "MEASURED" and out["days"] == 150
    c = out["cadence"]
    assert set(c) == {"1", "5", "20"}
    assert c["1"]["turnover"] >= c["20"]["turnover"]       # faster re-weights more
    for row in c.values():
        lo, hi = row["ci90"]
        assert lo <= hi
    assert all(0.0 <= p <= 1.0 for p in out["p_faster_beats_slower"].values())
    # The bound is the optimum over constant fractions: no constant book in the box beats it,
    # whatever the proxy (which re-weights) did -- its gap is signed.
    import numpy as np
    _s, _d, m = meta_rnd._matrix(_daily(150, seed=3))
    ret = m * meta_rnd.RISK_PER_R
    top = out["bound"]["hindsight_constant_fraction_log_growth"]
    rng = np.random.default_rng(0)
    for f in rng.uniform(0, meta_rnd.F_MAX, size=(200, ret.shape[1])):
        assert float(np.log1p(ret @ f).mean()) <= top + 1e-7
    assert "PROXY" in out["subject"]


def test_the_frontier_reports_the_cadence_and_bound_rows_when_measured(tmp_path, monkeypatch):
    monkeypatch.setattr(meta_rnd, "DESK", tmp_path)
    st = meta_rnd.cadence_and_bound(_daily(150, seed=3), boots=20)
    fr = meta_rnd.frontier({"ordering": {}, "cadence_and_bound": st})
    rows = {r["id"]: r for r in fr["limitations"]}
    assert rows["allocator_speed_vs_turnover"]["status"] == "MEASURED"
    assert rows["optimality_gap"]["status"] == "MEASURED"
    assert isinstance(rows["optimality_gap"]["result"]["gap"], float)


def test_representation_methods_compete_on_what_their_candidates_survived(tmp_path,
                                                                        monkeypatch):
    monkeypatch.setattr(meta_rnd, "DESK", tmp_path)
    (tmp_path / "reports").mkdir()
    rows = [{"family": "surprise", "used_by_candidates": 400, "survivors": 40},
            {"family": "pace", "used_by_candidates": 400, "survivors": 2},
            {"family": "fresh", "used_by_candidates": 1, "survivors": 0}]
    (tmp_path / "reports" / "REPRESENTATION_FORGE.json").write_text(
        json.dumps({"roi": {"rows": rows}}))
    fr = meta_rnd.frontier({"ordering": {}})
    r = {x["id"]: x for x in fr["limitations"]}["representation_novelty"]
    assert r["status"] == "MEASURED" and r["result"]["leader"] == "surprise"
    assert r["result"]["verdicts"]["fresh"] == "UNMEASURED"
    assert r["result"]["verdicts"]["pace"] == "TRAILS"


def _report(tmp_path, name, doc):
    (tmp_path / "reports").mkdir(exist_ok=True)
    (tmp_path / "reports" / name).write_text(json.dumps(doc))


def test_every_limitation_now_has_a_challenger_or_a_policy_block():
    for lim in meta_rnd.LIMITATIONS:
        assert lim.get("challenger") or lim.get("blocked_by"), lim["id"]


def test_trajectory_reuse_is_judged_against_cold_starts(tmp_path, monkeypatch):
    monkeypatch.setattr(meta_rnd, "DESK", tmp_path)
    _report(tmp_path, "MUTATION_YIELD.json", {"reuse_vs_cold": {
        "reuse": {"certified": 30, "failed": 270, "judged": 300},
        "cold": {"certified": 5, "failed": 995, "judged": 1000}}})
    r = {x["id"]: x for x in meta_rnd.frontier({"ordering": {}})["limitations"]}
    row = r["research_trajectories"]
    assert row["status"] == "MEASURED" and row["result"]["leader"] == "reuse"
    assert row["result"]["verdicts"]["cold"] == "TRAILS"


def test_record_ablation_names_organs_with_no_measured_product(tmp_path, monkeypatch):
    monkeypatch.setattr(meta_rnd, "DESK", tmp_path)
    _report(tmp_path, "MODULE_RENT_RESEARCH.json", {"rows": [
        {"module": "a.py", "compute_h_30d": 9.0, "candidates_30d": 300, "survivors_30d": 0,
         "admissions_30d": 0},
        {"module": "b.py", "compute_h_30d": 2.0, "candidates_30d": 50, "survivors_30d": 3,
         "admissions_30d": 9},
        {"module": "c.py", "compute_h_30d": None, "survivors_30d": None},
        {"module": "d.py", "compute_h_30d": 5.0, "candidates_30d": 0, "survivors_30d": 0,
         "admissions_30d": 0},
        {"module": "e.py", "compute_h_30d": 1.0, "candidates_30d": 2, "survivors_30d": 0,
         "admissions_30d": 0}]})
    r = {x["id"]: x for x in meta_rnd.frontier({"ordering": {}})["limitations"]}
    res = r["component_ablation"]["result"]
    assert r["component_ablation"]["status"] == "MEASURED"
    # d.py has no candidates: unbounded, never removable; e.py's 3/2 bound is capped at 1.
    assert res["organs_measured"] == 4 and res["removable_on_record"] == 2
    assert res["zero_candidate_unbounded"] == ["d.py"]
    assert res["top"][1]["survivor_rate_upper_95"] == 1.0
    assert res["top"][0] == {"module": "a.py", "compute_h_30d": 9.0, "candidates_30d": 300,
                             "survivor_rate_upper_95": 0.01}


def test_discovery_methods_are_read_from_the_owners_report(tmp_path, monkeypatch):
    monkeypatch.setattr(meta_rnd, "DESK", tmp_path)
    r = {x["id"]: x for x in meta_rnd.frontier({"ordering": {}})["limitations"]}
    assert r["dataset_discovery_method"]["status"] == "UNMEASURED"
    _report(tmp_path, "SOURCE_FRONTIER.json", {"by_discovery_method": [
        {"method": "catalogue", "sources": 200, "testable": 60, "compute_h": 2.0},
        {"method": "crawl", "sources": 200, "testable": 10, "compute_h": 2.0},
        {"method": "ask", "sources": 10, "testable": 1, "compute_h": "n/a"}]})
    r = {x["id"]: x for x in meta_rnd.frontier({"ordering": {}})["limitations"]}
    res = r["dataset_discovery_method"]["result"]
    assert res["leader"] == "catalogue" and res["leader_per_h"] == "catalogue"
    assert res["testable_per_h"] == {"catalogue": 30.0, "crawl": 5.0}
    assert res["compute_h"] == {"catalogue": 2.0, "crawl": 2.0, "ask": None}


def test_mutation_yield_splits_reuse_from_cold_starts():
    from research import mutation_yield as my
    rows = {"a": {"operator": "step_lookback_up"}, "b": {"operator": None}}
    verd = {"a": {"fate": "CERTIFIED"}, "b": {"fate": "FAILED"}, "c": {"fate": "FAILED"},
            "d": {"fate": "BORN"}}
    out = my.reuse_vs_cold(rows, verd)
    assert out["reuse"]["certified"] == 1 and out["reuse"]["judged"] == 1
    assert out["cold"]["failed"] == 2 and out["cold"]["judged"] == 2


def test_the_coevolution_leg_floor_covers_the_challenger():
    src = (DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    floor = src[src.index("LEG_BUDGET_FLOOR_SEC: dict[str, int] = {"):]
    floor = floor[:floor.index("\n}\n")]
    assert '"coevolution": 1_140' in floor
    from research import hourly_cycle as hc
    assert hc._leg_floor_s("coevolution") >= hc._self_stop_floor_s(
        ("--budget-s", str(int(fmc.BUDGET_S + fmc.H2H_BUDGET_S))))
