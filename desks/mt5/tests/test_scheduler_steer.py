"""Method competition changes the REAL scheduler (Tier S audit AC13 and I12).

The arena's verdicts and the Red Queen's adopted scheduler champion must move the weights
`cycle_pricing.build_plan` spends the hour by; researcher_market and meta_benchmark get budget
authority only as a scored tournament with a seeded random holdout, whose holdout-versus-treated
comparison is published. Weights are two-sided, the total never falls, and a suspended organ
carries no authority.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cycle_pricing as cp  # type: ignore[import-not-found]  # noqa: E402
import tier_s as ts  # type: ignore[import-not-found]  # noqa: E402

from libs.tiers import program_evolution as pe  # noqa: E402
from libs.tiers import scheduler_tournament as tour  # noqa: E402

NOW = datetime(2026, 10, 6, 12, 5, tzinfo=UTC)


def _isolate_tier_s(tmp_path: Path, monkeypatch: Any, *, arena: dict[str, Any] | None = None,
                    red_queen: dict[str, Any] | None = None,
                    suspended: tuple[str, ...] = ()) -> None:
    state, out = tmp_path / "state", tmp_path / "reports_tier_s"
    state.mkdir()
    out.mkdir()
    monkeypatch.setattr(ts, "NOW", NOW)
    monkeypatch.setattr(ts, "STATE", state)
    monkeypatch.setattr(ts, "OUT_DIR", out)
    monkeypatch.setattr(ts, "ARM_VERDICTS", tmp_path / "ARM_VERDICTS.json")
    for name in ("HGRAPH", "COMPUTE", "GATE_LEDGER"):
        p = tmp_path / f"{name}.jsonl"
        p.write_text("", encoding="utf-8")
        monkeypatch.setattr(ts, name, p)
    if arena is not None:
        (tmp_path / "ARM_VERDICTS.json").write_text(json.dumps(arena), encoding="utf-8")
    if red_queen is not None:
        (out / "RED_QUEEN.json").write_text(json.dumps(red_queen), encoding="utf-8")
    monkeypatch.setattr(ts.authority, "suspended", lambda organ, *a, **k: organ in suspended)


def _arena(verdicts: dict[str, str]) -> dict[str, Any]:
    return {"at": NOW.isoformat(), "leader": "mutate_survivor",
            "arms": {a: {"verdict": v} for a, v in verdicts.items()}}


def _isolate_pricing(tmp_path: Path, monkeypatch: Any, steer_doc: dict[str, Any] | None
                     ) -> None:
    for name in ("META", "BANDIT", "POLICY"):
        monkeypatch.setattr(cp, name, tmp_path / f"{name}.json")
    ledger = tmp_path / "compute_ledger.jsonl"
    # every leg ran recently, so none is pulled forward as a scout and order follows price
    ledger.write_text("".join(json.dumps({"at": datetime.now(UTC).isoformat(timespec="seconds"),
                                          "run": leg, "wall_s": 30.0}) + "\n" for leg in BASES),
                      encoding="utf-8")
    monkeypatch.setattr(cp, "LEDGER", ledger)
    monkeypatch.setattr(cp, "OUT", tmp_path / "CYCLE_PRICING.json")
    steer = tmp_path / "SCHEDULER_STEER.json"
    if steer_doc is not None:
        steer.write_text(json.dumps(steer_doc), encoding="utf-8")
    monkeypatch.setattr(cp, "STEER", steer)
    for fn in ("_factory_prices", "_alpha_rank_prices", "_evig_prices", "_meta_prices"):
        monkeypatch.setattr(cp, fn, lambda: ({}, "isolated"))
    monkeypatch.setattr(cp, "_bandit_prices", dict)
    monkeypatch.setattr(cp, "_researcher_prices", dict)
    monkeypatch.setattr(cp, "_policy_factors", lambda: ({}, False))
    # judge0 is a validation (judge-side) leg; every other leg is generation / rest
    monkeypatch.setattr(cp, "_department_of",
                        lambda leg: "validate" if leg.startswith("judge") else "rest")


BASES = {"alpha_evolution": 600, "deepen": 600, "judge0": 600,
         **{f"leg{i}": 600 for i in range(6)}}


# ------------------------------------------------------------------------------------- AC13

def test_an_arena_verdict_changes_the_weights_both_ways(tmp_path: Path, monkeypatch: Any) -> None:
    _isolate_tier_s(tmp_path, monkeypatch, arena=_arena({
        "mutate_survivor": "LEADS", "combine_survivors": "KEEP", "new_mechanism": "KEEP",
        "external_screen": "TRAILS", "alt_data_hypothesis": "KEEP", "failure_derived": "KEEP"}))
    rep = ts.organ_steer()
    legs = rep["legs"]
    assert legs["alpha_evolution"]["due"] > 1.0, "the LEADS arm's leg did not gain weight"
    # deepen is a GENERATION leg (discovery department): a TRAILS verdict may not take it below
    # 1.0 -- backpressure goes to the judge only
    assert legs["deepen"]["due"] == 1.0
    assert rep["contestants"]["arena"]["authority"] > 0
    # nothing measured yet: TRIAL mode, not authoritative. One movable leg cannot be split into a
    # holdout and a trial slice, so nothing runs on a weight this hour.
    assert rep["comparison"]["primary"] == "UNMEASURED" and rep["mode"] == "TRIAL"
    assert not rep["authoritative"] and not rep["withdrawn"]
    assert set(rep["weights"].values()) == {1.0}
    # and it was remembered for the tournament to score next hour
    st = json.loads((tmp_path / "state" / "scheduler_steer.json").read_text("utf-8"))
    assert st["assignments"][-1]["tilts"]["arena"]["alpha_evolution"] > 1.0


def test_without_arena_verdicts_nothing_moves(tmp_path: Path, monkeypatch: Any) -> None:
    _isolate_tier_s(tmp_path, monkeypatch, arena=_arena({"mutate_survivor": "KEEP"}))
    rep = ts.organ_steer()
    assert rep["weights"] == {}


def test_a_red_queen_adoption_changes_the_weights(tmp_path: Path, monkeypatch: Any) -> None:
    rq = {"generated_utc": NOW.isoformat(), "architecture_challengers": {"scheduler": {
        "beats_incumbent_heldout": True, "heldout_lift": 0.02,
        "adopted_split": {"miner:alpha": 0.7, "miner:beta": 0.2, "miner:gamma": 0.1}}}}
    _isolate_tier_s(tmp_path, monkeypatch, red_queen=rq)
    (tmp_path / "state" / "researcher_prices.json").write_text(json.dumps({
        "generated_utc": NOW.isoformat(), "leg_prices": {},
        "researchers": {"miner:alpha": {"leg": "leg0"}, "miner:beta": {"leg": "leg1"},
                        "miner:gamma": {"leg": "leg2"}}}), encoding="utf-8")
    rep = ts.organ_steer()
    due = {lg: r["due"] for lg, r in rep["legs"].items()}
    assert due["leg0"] > 1.0, due
    assert due["leg2"] == 1.0, "a generation leg was weighted below par"
    assert "adopted" in rep["inputs"]["red_queen"]


def test_a_suspended_red_queen_carries_no_authority(tmp_path: Path, monkeypatch: Any) -> None:
    rq = {"generated_utc": NOW.isoformat(), "architecture_challengers": {"scheduler": {
        "adopted_split": {"miner:alpha": 0.9, "miner:beta": 0.1}}}}
    _isolate_tier_s(tmp_path, monkeypatch, red_queen=rq, suspended=("red_queen",))
    (tmp_path / "state" / "researcher_prices.json").write_text(json.dumps({
        "generated_utc": NOW.isoformat(),
        "researchers": {"miner:alpha": {"leg": "leg0"}, "miner:beta": {"leg": "leg1"}}}),
        encoding="utf-8")
    rep = ts.organ_steer()
    assert rep["weights"] == {}
    assert rep["dropped_suspended"] == ["red_queen"]
    assert rep["contestants"]["red_queen"]["suspended"] is True
    assert rep["contestants"]["red_queen"]["authority"] == 0.0


def test_the_champion_publishes_the_split_it_would_spend_today() -> None:
    days = {f"2026-09-{d:02d}": {"a": [10, 5], "b": [10, 1]} for d in range(1, 9)}
    split = pe.current_split({"rule": "posterior_mean", "prior": 2.0, "half_life_days": 7.0,
                              "explore_floor": 0.1}, days)
    assert split["a"] > split["b"] and abs(sum(split.values()) - 1.0) < 1e-9
    assert pe.current_split({"rule": "as_spent"}, days) == {}


def test_the_weights_reach_the_real_scheduler_two_sided_and_never_cut(
        tmp_path: Path, monkeypatch: Any) -> None:
    _isolate_pricing(tmp_path, monkeypatch, None)
    base = cp.build_plan(dict(BASES))
    doc = {"generated_utc": datetime.now(UTC).isoformat(), "hour": "h",
           "weights": {"leg0": 1.5, "judge0": 0.5}, "withdrawn": False}
    _isolate_pricing(tmp_path, monkeypatch, doc)
    steered = cp.build_plan(dict(BASES))
    b, s = base["legs"], steered["legs"]
    assert s["leg0"]["score"] > b["leg0"]["score"], "a weighted-up leg's price did not rise"
    assert s["judge0"]["score"] < b["judge0"]["score"], "a down-weighted judge leg did not fall"
    assert "scheduler_steer" in s["leg0"]["priced_by"]
    assert steered["order"].index("leg0") < steered["order"].index("judge0")
    assert s["leg0"]["price_factor"] > 1.0
    # NEVER A CUT: every leg keeps its base and the hour's total never falls
    assert all(v["planned_s"] >= v["base_s"] for v in s.values())
    assert steered["totals"]["never_reduced"]
    assert steered["sources"]["scheduler_steer"] is True


def test_a_generation_leg_at_the_minimum_weight_keeps_its_slot_and_seconds(
        tmp_path: Path, monkeypatch: Any) -> None:
    """BACKPRESSURE GOES TO THE JUDGE ONLY: a 0.5 weight on a mining / generation leg must not run
    it later or shorter -- the consumer floors it at 1.0 whatever the artifact says."""
    _isolate_pricing(tmp_path, monkeypatch, None)
    base = cp.build_plan(dict(BASES))
    doc = {"generated_utc": datetime.now(UTC).isoformat(), "hour": "h",
           "weights": {"leg3": 0.5, "deepen": 0.5}, "withdrawn": False}
    _isolate_pricing(tmp_path, monkeypatch, doc)
    steered = cp.build_plan(dict(BASES))
    for leg in ("leg3", "deepen"):
        assert steered["order"].index(leg) == base["order"].index(leg), "order slot moved"
        assert steered["legs"][leg]["planned_s"] == base["legs"][leg]["planned_s"]
        assert steered["legs"][leg]["score"] == base["legs"][leg]["score"]
    # and the tournament itself never proposes one below par
    doc2 = tour.steer({"researcher_market": {"gen": 0.5, "judge": 0.5, "other": 1.5}}, {}, [],
                      "h", down_ok=["judge"])
    assert doc2["legs"]["gen"]["due"] == 1.0 and doc2["legs"]["judge"]["due"] < 1.0


def test_a_withdrawn_or_stale_steer_moves_nothing(tmp_path: Path, monkeypatch: Any) -> None:
    _isolate_pricing(tmp_path, monkeypatch, {"generated_utc": datetime.now(UTC).isoformat(),
                                             "weights": {"leg0": 1.5}, "withdrawn": True})
    assert cp._steer_weights()[0] == {}
    old = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
    _isolate_pricing(tmp_path, monkeypatch, {"generated_utc": old, "weights": {"leg0": 1.5}})
    assert cp._steer_weights()[0] == {}


# --------------------------------------------------------------------------------------- I12

def test_the_holdout_is_a_seeded_random_slice_on_the_prior_allocation() -> None:
    legs = [f"leg{i}" for i in range(20)]
    h1 = tour.holdout(legs, "2026-10-06T12")
    assert h1 == tour.holdout(legs, "2026-10-06T12"), "the draw is not reproducible from its seed"
    assert len(h1) == round(tour.HOLDOUT_SHARE * 20)
    assert any(tour.holdout(legs, f"2026-10-06T{h:02d}") != h1 for h in range(13, 20)), \
        "the slice is not re-drawn each hour"
    doc = tour.steer({"researcher_market": {lg: 1.4 if i % 2 else 0.6
                                            for i, lg in enumerate(legs)}},
                     {}, [], "2026-10-06T12", down_ok=legs)
    for lg in doc["holdout"]:
        assert doc["weights"][lg] == 1.0 and doc["legs"][lg]["due"] != 1.0
    assert doc["comparison"]["primary"] == "UNMEASURED"


def _history(good: str, bad: str, n: int = 6) -> list[dict[str, Any]]:
    """Hours where `good`'s tilts point at the legs that then produced and `bad`'s point away."""
    out = []
    for h in range(n):
        out.append({"hour": f"h{h}",
                    "tilts": {good: {"leg0": 1.4, "leg1": 0.6},
                              bad: {"leg0": 0.6, "leg1": 1.4}},
                    "legs": {}, "outcomes": {"leg0": 10.0 + h, "leg1": 1.0, "leg2": 5.0}})
    return out


def test_the_tournament_moves_authority_both_ways() -> None:
    props = {"researcher_market": {"leg0": 1.3}, "meta_benchmark": {"leg1": 1.3}}
    doc = tour.steer(props, {}, _history("researcher_market", "meta_benchmark"), "h9")
    c = doc["contestants"]
    assert c["researcher_market"]["status"] == c["meta_benchmark"]["status"] == "MEASURED"
    assert c["researcher_market"]["authority"] > 0.5 > c["meta_benchmark"]["authority"]
    flipped = tour.steer(props, {}, _history("meta_benchmark", "researcher_market"), "h9")
    assert flipped["contestants"]["meta_benchmark"]["authority"] > \
        flipped["contestants"]["researcher_market"]["authority"]
    # a suspended market loses its authority outright, whatever its record
    sus = tour.steer(props, {"researcher_market": True},
                     _history("researcher_market", "meta_benchmark"), "h9")
    assert sus["contestants"]["researcher_market"]["authority"] == 0.0
    assert "leg0" not in sus["weights"]


def _arms(treated: float, holdout: float, n: int = 6) -> list[dict[str, Any]]:
    return [{"outcomes": {"a": treated + 0.01 * h, "b": holdout + 0.01 * h},
             "legs": {"a": {"due": 1.3, "applied": 1.3, "arm": "trial"},
                      "b": {"due": 1.3, "applied": 1.0, "arm": "holdout"}}}
            for h in range(n)]


def test_an_inconclusive_comparison_runs_only_the_trial_slice() -> None:
    """UNMEASURED / UNDECIDED: the seeded trial slice (the holdout's size) runs on the weights,
    every other leg is neutral, and nothing claims authority."""
    legs = [f"g{i}" for i in range(20)]
    props = {"researcher_market": {lg: 1.4 if i % 2 else 0.6 for i, lg in enumerate(legs)}}
    for hist in ([], _arms(5.0, 5.0, n=2), _arms(5.0, 5.0)):   # unmeasured, too few, undecided
        doc = tour.steer(props, {}, hist, "h9", down_ok=legs)
        assert doc["comparison"]["primary"] in ("UNMEASURED", "UNDECIDED")
        assert doc["mode"] == "TRIAL" and not doc["authoritative"] and not doc["withdrawn"]
        moved = {lg for lg, w in doc["weights"].items() if w != 1.0}
        assert moved == set(doc["trial"]) and len(doc["trial"]) == len(doc["holdout"]) == 4
        assert not moved & set(doc["holdout"])
        assert doc["trial"] == tour.trial(sorted(set(legs) - set(doc["holdout"])), "h9", 4)
    admitted = tour.steer(props, {}, _arms(9.0, 1.0), "h9", down_ok=legs)
    assert admitted["mode"] == "ADMITTED" and admitted["authoritative"]
    treated = [lg for lg, r in admitted["legs"].items() if r["arm"] == "treated"]
    assert len(treated) == 16 and all(admitted["weights"][lg] != 1.0 for lg in treated)
    assert all(admitted["weights"][lg] == 1.0 for lg in admitted["holdout"])


def test_generation_legs_stay_up_only_inside_the_trial_slice() -> None:
    legs = [f"g{i}" for i in range(20)]
    props = {"researcher_market": {lg: 1.4 if i % 2 else 0.6 for i, lg in enumerate(legs)}}
    for hour in ("h1", "h2", "h3"):
        doc = tour.steer(props, {}, [], hour)          # no down_ok: every leg is generation
        assert all(w >= 1.0 for w in doc["weights"].values())


def test_the_trial_slice_turns_unmeasured_into_admitted() -> None:
    """The experiment can reach a verdict: start with no history, let the desk respond to the
    weights (a leg that runs on a weight above 1 produces more), and the comparison of trial
    leg-hours against held-out ones moves UNMEASURED -> ADMITTED, after which every non-holdout
    leg is treated."""
    legs = [f"g{i}" for i in range(20)]
    props = {"researcher_market": {lg: 1.4 if i % 2 else 0.6 for i, lg in enumerate(legs)}}
    hist: list[dict[str, Any]] = []
    modes = []
    t0 = datetime(2026, 10, 6, tzinfo=UTC)
    for h in range(12):
        now = t0 + timedelta(hours=h)
        doc = tour.steer(props, {}, hist, f"h{h}", down_ok=legs, now=now)
        modes.append((doc["mode"], doc["comparison"]["primary"]))
        if doc["mode"] == "ADMITTED":
            break
        outcomes = {lg: (10.0 if r["applied"] > 1.0 else 2.0) + 0.1 * ((h + i) % 3)
                    for i, (lg, r) in enumerate(doc["legs"].items())}
        hist.append({"at": now.isoformat(), "legs": {lg: {k: r[k] for k in
                                                          ("due", "applied", "arm")}
                                                     for lg, r in doc["legs"].items()},
                     "outcomes": outcomes})
    assert modes[0] == ("TRIAL", "UNMEASURED")
    assert doc["mode"] == "ADMITTED" and doc["authoritative"], modes
    c = doc["comparison"]["up"]
    assert c["n_treated"] >= 3 and c["n_control"] >= 3 and c["mean_treated"] > c["mean_holdout"]


def test_a_rejected_comparison_is_neutral_cools_down_then_retries() -> None:
    t0 = datetime(2026, 10, 6, tzinfo=UTC)
    hist = [{**a, "at": (t0 - timedelta(hours=10 - i)).isoformat()}
            for i, a in enumerate(_arms(1.0, 9.0))]
    legs = [f"g{i}" for i in range(10)]
    props = {"researcher_market": {lg: 1.4 if i % 2 else 0.6 for i, lg in enumerate(legs)}}
    doc = tour.steer(props, {}, hist, "h0", down_ok=legs, now=t0)
    assert doc["comparison"]["up"]["verdict"] == "REJECTED" and doc["mode"] == "REJECTED"
    assert doc["withdrawn"] and not doc["authoritative"]
    assert set(doc["weights"].values()) == {1.0}
    assert doc["rejected_at"] == t0.isoformat()
    cool = tour.steer(props, {}, hist, "h1", down_ok=legs, rejected_at=doc["rejected_at"],
                      now=t0 + timedelta(hours=1))
    assert cool["mode"] == "COOLDOWN" and set(cool["weights"].values()) == {1.0}
    later = t0 + timedelta(hours=tour.COOLDOWN_H + 1)
    retry = tour.steer(props, {}, hist, "h99", down_ok=legs, rejected_at=doc["rejected_at"],
                       now=later)
    # the pre-rejection evidence no longer counts: the trial slice retries on fresh evidence
    assert retry["mode"] == "TRIAL" and retry["comparison"]["primary"] == "UNMEASURED"
    assert any(w != 1.0 for w in retry["weights"].values())


def test_credited_elogw_is_reported_beside_births() -> None:
    hist = []
    for h in range(5):
        a = _arms(5.0, 5.0, n=1)[0]
        a["elogw_outcomes"] = {"a": 0.002 + 0.0001 * h, "b": 0.0001 * h}
        hist.append(a)
    cmp_ = tour.holdout_comparison(hist)
    assert cmp_["elogw"]["n_treated"] == 5 and cmp_["elogw"]["n_control"] == 5
    assert cmp_["elogw"]["mean_treated"] > cmp_["elogw"]["mean_holdout"]
    assert cmp_["primary"] == cmp_["up"]["verdict"]       # births decide; elogw only reports


def test_weights_are_bounded_and_mean_one() -> None:
    w = tour.combine({"a": {"x": 1.5, "y": 0.5, "z": 1.5}}, {"a": 1.0})
    assert all(0.5 <= v <= 1.5 for v in w.values())
    assert abs(sum(w.values()) / len(w) - 1.0) < 0.05


def test_elapsed_hours_are_scored_from_births_per_cpu_hour(
        tmp_path: Path, monkeypatch: Any) -> None:
    _isolate_tier_s(tmp_path, monkeypatch, arena=_arena({"mutate_survivor": "LEADS"}))
    t0 = NOW - timedelta(hours=2)
    (tmp_path / "state" / "scheduler_steer.json").write_text(json.dumps({"assignments": [{
        "hour": "old", "at": t0.isoformat(), "outcomes": None,
        "legs": {"alpha_evolution": {"due": 1.1, "applied": 1.1, "arm": "treated"}},
        "tilts": {"arena": {"alpha_evolution": 1.1}}}]}), encoding="utf-8")
    (tmp_path / "state" / "researcher_prices.json").write_text(json.dumps({
        "generated_utc": NOW.isoformat(),
        "researchers": {"miner:alpha_evolution": {"leg": "alpha_evolution"}}}), encoding="utf-8")
    born = [{"at": (t0 + timedelta(minutes=10 + i)).isoformat(), "source": "miner:alpha_evolution",
             "symbol": "EURUSD", "family": f"fam{i}", "fate": "BORN"} for i in range(3)]
    ts.HGRAPH.write_text("".join(json.dumps(r) + "\n" for r in born), encoding="utf-8")
    ts.COMPUTE.write_text(json.dumps({"at": (t0 + timedelta(minutes=30)).isoformat(),
                                      "run": "alpha_evolution", "cpu_s": 1800.0}) + "\n",
                          encoding="utf-8")
    rep = ts.organ_steer()
    st = json.loads((tmp_path / "state" / "scheduler_steer.json").read_text("utf-8"))
    old = next(a for a in st["assignments"] if a["hour"] == "old")
    assert old["outcomes"] == {"alpha_evolution": 6.0}   # 3 novel births in half a CPU-hour
    assert rep["assignments_scored"] == 1


def test_duplicate_births_do_not_raise_the_score(tmp_path: Path, monkeypatch: Any) -> None:
    """Novelty-deflated: three copies of one (symbol, family) earn 1 + 1/sqrt2 + 1/sqrt3, less
    than three distinct births in the same CPU, and a pair born before earns less again."""
    def score(families: list[str], prior: int = 0) -> float:
        sub = tmp_path / f"run{len(list(tmp_path.iterdir()))}"
        sub.mkdir()
        _isolate_tier_s(sub, monkeypatch, arena=_arena({"mutate_survivor": "LEADS"}))
        t0 = NOW - timedelta(hours=2)
        (sub / "state" / "scheduler_steer.json").write_text(json.dumps({"assignments": [{
            "hour": "old", "at": t0.isoformat(), "outcomes": None,
            "legs": {"alpha_evolution": {"due": 1.1, "applied": 1.1, "arm": "treated"}},
            "tilts": {}}]}), encoding="utf-8")
        (sub / "state" / "researcher_prices.json").write_text(json.dumps({
            "generated_utc": NOW.isoformat(),
            "researchers": {"miner:alpha_evolution": {"leg": "alpha_evolution"}}}),
            encoding="utf-8")
        rows = [{"at": (t0 - timedelta(hours=5)).isoformat(), "source": "miner:other",
                 "symbol": "EURUSD", "family": families[0], "fate": "BORN"}] * prior
        rows += [{"at": (t0 + timedelta(minutes=10 + i)).isoformat(),
                  "source": "miner:alpha_evolution", "symbol": "EURUSD", "family": f,
                  "fate": "BORN"} for i, f in enumerate(families)]
        ts.HGRAPH.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        ts.COMPUTE.write_text(json.dumps({"at": (t0 + timedelta(minutes=30)).isoformat(),
                                          "run": "alpha_evolution", "cpu_s": 1800.0}) + "\n",
                              encoding="utf-8")
        ts.organ_steer()
        st = json.loads((sub / "state" / "scheduler_steer.json").read_text("utf-8"))
        old = next(a for a in st["assignments"] if a["hour"] == "old")
        return float(old["outcomes"]["alpha_evolution"])
    distinct = score(["f1", "f2", "f3"])
    dupes = score(["f1", "f1", "f1"])
    assert distinct == 6.0
    assert dupes < distinct
    assert abs(dupes - 2.0 * (1 + 2 ** -0.5 + 3 ** -0.5)) < 1e-4
    assert score(["f1"], prior=3) < score(["f1"])     # a pair born before is worth less
