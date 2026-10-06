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


def _isolate_pricing(tmp_path: Path, monkeypatch: Any, steer_doc: dict[str, Any] | None) -> None:
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
    monkeypatch.setattr(cp, "_department_of", lambda leg: "rest")


BASES = {"alpha_evolution": 600, "deepen": 600, **{f"leg{i}": 600 for i in range(6)}}


# ------------------------------------------------------------------------------------- AC13

def test_an_arena_verdict_changes_the_weights_both_ways(tmp_path: Path, monkeypatch: Any) -> None:
    _isolate_tier_s(tmp_path, monkeypatch, arena=_arena({
        "mutate_survivor": "LEADS", "combine_survivors": "KEEP", "new_mechanism": "KEEP",
        "external_screen": "TRAILS", "alt_data_hypothesis": "KEEP", "failure_derived": "KEEP"}))
    rep = ts.organ_steer()
    legs = rep["legs"]
    assert legs["alpha_evolution"]["due"] > 1.0, "the LEADS arm's leg did not gain weight"
    assert legs["deepen"]["due"] < 1.0, "the TRAILS arm's leg did not lose weight (two-sided)"
    assert rep["contestants"]["arena"]["authority"] > 0
    # the artifact the scheduler reads carries the APPLIED weights (held-out legs at 1.0)
    for leg, row in legs.items():
        assert rep["weights"][leg] == (1.0 if row["arm"] == "holdout" else row["due"])
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
    assert due["leg0"] > 1.0 > due["leg2"], due
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
           "weights": {"leg0": 1.5, "leg1": 0.5}, "withdrawn": False}
    _isolate_pricing(tmp_path, monkeypatch, doc)
    steered = cp.build_plan(dict(BASES))
    b, s = base["legs"], steered["legs"]
    assert s["leg0"]["score"] > b["leg0"]["score"], "a weighted-up leg's price did not rise"
    assert s["leg1"]["score"] < b["leg1"]["score"], "a weighted-down leg's price did not fall"
    assert "scheduler_steer" in s["leg0"]["priced_by"]
    assert steered["order"].index("leg0") < steered["order"].index("leg1")
    assert s["leg0"]["price_factor"] > 1.0
    # NEVER A CUT: every leg keeps its base and the hour's total never falls
    assert all(v["planned_s"] >= v["base_s"] for v in s.values())
    assert steered["totals"]["never_reduced"]
    assert steered["sources"]["scheduler_steer"] is True


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
                     {}, [], "2026-10-06T12")
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


def test_a_rejected_holdout_comparison_withdraws_the_steer() -> None:
    hist = []
    for h in range(6):
        hist.append({"outcomes": {"a": 1.0 + 0.01 * h, "b": 9.0 + 0.01 * h},
                     "legs": {"a": {"due": 1.3, "arm": "treated"},
                              "b": {"due": 1.3, "arm": "holdout"}}})
    doc = tour.steer({"researcher_market": {"x": 1.4, "y": 0.6}}, {}, hist, "h9")
    assert doc["comparison"]["up"]["verdict"] == "REJECTED"
    assert doc["withdrawn"] and not doc["authoritative"]
    assert set(doc["weights"].values()) == {1.0}


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
