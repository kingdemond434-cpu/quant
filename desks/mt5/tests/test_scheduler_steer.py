"""Method competition changes the REAL scheduler (Tier S audit AC13 and I12).

The arena's verdicts and the Red Queen's adopted scheduler champion move the weights
`cycle_pricing.build_plan` spends the hour by; researcher_market and meta_benchmark hold budget
authority only through a scored tournament with a seeded random holdout and a seeded trial slice,
judged by a sequentially valid test on APPLIED weights. Backpressure goes to the judge only, the
applied weights are zero-sum, a contestant needs three scored hours for any authority, and a
suspended organ (the arena included) carries none. A validator the real-gauntlet arena adopts also
takes over the research pre-judge screen.
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
    monkeypatch.setattr(ts, "STEER_APPLIED", tmp_path / "steer_applied.jsonl")
    monkeypatch.setattr(ts, "FACTORY_CONTRACTS", tmp_path / "FACTORY_CONTRACTS.json")
    monkeypatch.setattr(ts, "shadow_rows", dict)
    monkeypatch.setattr(ts, "survivors", dict)


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
    monkeypatch.setattr(cp, "STEER_APPLIED", tmp_path / "steer_applied.jsonl")
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


# ------------------------------------------------------------------------------------- helpers

def _warm(tilts: dict[str, dict[str, float]], n: int = 3,
          start: datetime | None = None) -> list[dict[str, Any]]:
    """`n` scored hours in which every leg a contestant tilted UP then produced and every other
    leg did not -- enough evidence for authority (MIN_HOURS), and no experiment arms."""
    legs = {lg for t in tilts.values() for lg in t} | {"_bystander"}
    t0 = start or NOW - timedelta(hours=n + 2)
    out = []
    for h in range(n):
        ups = {lg for t in tilts.values() for lg, w in t.items() if w > 1.0}
        out.append({"hour": f"w{h}", "at": (t0 + timedelta(hours=h)).isoformat(), "legs": {},
                    "tilts": tilts, "outcomes": {lg: (10.0 if lg in ups else 1.0) + 0.1 * h
                                                 for lg in legs}})
    return out


def _seed_state(tmp_path: Path, assignments: list[dict[str, Any]]) -> None:
    (tmp_path / "state" / "scheduler_steer.json").write_text(
        json.dumps({"assignments": assignments}), encoding="utf-8")


LEGS20 = [f"g{i}" for i in range(20)]
ALT = {"researcher_market": {lg: 1.4 if i % 2 else 0.6 for i, lg in enumerate(LEGS20)}}


# ------------------------------------------------------------------------------------- AC13

def test_an_arena_verdict_moves_the_weights_once_it_has_earned_authority(
        tmp_path: Path, monkeypatch: Any) -> None:
    verdicts = {"mutate_survivor": "LEADS", "combine_survivors": "KEEP", "new_mechanism": "KEEP",
                "external_screen": "TRAILS", "alt_data_hypothesis": "KEEP",
                "failure_derived": "KEEP"}
    _isolate_tier_s(tmp_path, monkeypatch, arena=_arena(verdicts))
    cold = ts.organ_steer()
    # no scored hours yet: ZERO authority, nothing moves
    assert cold["contestants"]["arena"]["status"] == "INSUFFICIENT_HOURS"
    assert cold["contestants"]["arena"]["authority"] == 0.0
    assert all(r["due"] == 1.0 for r in cold["legs"].values())
    sub = tmp_path / "warm"
    sub.mkdir()
    _isolate_tier_s(sub, monkeypatch, arena=_arena(verdicts))
    _seed_state(sub, _warm({"arena": {"alpha_evolution": 1.0833, "deepen": 0.9375}}))
    rep = ts.organ_steer()
    assert rep["contestants"]["arena"]["status"] == "MEASURED"
    assert rep["contestants"]["arena"]["authority"] == 1.0
    legs = rep["legs"]
    assert legs["alpha_evolution"]["due"] > 1.0, "the LEADS arm's leg did not gain weight"
    # deepen is a GENERATION leg: a TRAILS verdict may not take it below 1.0
    assert legs["deepen"]["due"] == 1.0
    assert rep["mode"] == "TRIAL" and not rep["authoritative"]
    assert rep["applied_mean"] == 1.0


def test_without_arena_verdicts_nothing_moves(tmp_path: Path, monkeypatch: Any) -> None:
    _isolate_tier_s(tmp_path, monkeypatch, arena=_arena({"mutate_survivor": "KEEP"}))
    rep = ts.organ_steer()
    assert rep["weights"] == {}


def test_a_red_queen_adoption_moves_the_weights(tmp_path: Path, monkeypatch: Any) -> None:
    rq = {"generated_utc": NOW.isoformat(), "architecture_challengers": {"scheduler": {
        "beats_incumbent_heldout": True, "heldout_lift": 0.02,
        "adopted_split": {"miner:alpha": 0.7, "miner:beta": 0.2, "miner:gamma": 0.1}}}}
    _isolate_tier_s(tmp_path, monkeypatch, red_queen=rq)
    (tmp_path / "state" / "researcher_prices.json").write_text(json.dumps({
        "generated_utc": NOW.isoformat(), "leg_prices": {},
        "researchers": {"miner:alpha": {"leg": "leg0"}, "miner:beta": {"leg": "leg1"},
                        "miner:gamma": {"leg": "leg2"}}}), encoding="utf-8")
    _seed_state(tmp_path, _warm({"red_queen": {"leg0": 1.5, "leg2": 0.5}}))
    rep = ts.organ_steer()
    due = {lg: r["due"] for lg, r in rep["legs"].items()}
    assert due["leg0"] > 1.0, due
    assert due["leg2"] == 1.0, "a generation leg was weighted below par"
    assert "adopted" in rep["inputs"]["red_queen"]


def test_a_suspended_organ_carries_no_authority_but_is_still_scored(
        tmp_path: Path, monkeypatch: Any) -> None:
    rq = {"generated_utc": NOW.isoformat(), "architecture_challengers": {"scheduler": {
        "adopted_split": {"miner:alpha": 0.9, "miner:beta": 0.1}}}}
    _isolate_tier_s(tmp_path, monkeypatch, red_queen=rq, suspended=("red_queen",))
    (tmp_path / "state" / "researcher_prices.json").write_text(json.dumps({
        "generated_utc": NOW.isoformat(),
        "researchers": {"miner:alpha": {"leg": "leg0"}, "miner:beta": {"leg": "leg1"}}}),
        encoding="utf-8")
    _seed_state(tmp_path, _warm({"red_queen": {"leg0": 1.5}}))
    rep = ts.organ_steer()
    assert all(w == 1.0 for w in rep["weights"].values())
    assert rep["dropped_suspended"] == ["red_queen"]
    row = rep["contestants"]["red_queen"]
    assert row["suspended"] is True and row["authority"] == 0.0 and row["mean_gain"] is not None
    st = json.loads((tmp_path / "state" / "scheduler_steer.json").read_text("utf-8"))
    assert "red_queen" in st["assignments"][-1]["tilts"], "a suspended organ must stay scored"


def test_the_arena_can_be_suspended_through_its_contract() -> None:
    from libs.tiers import authority
    ledger = json.loads((_ROOT / "docs" / "research" / "tier_s_program.json").read_text("utf-8"))
    row = next(r for r in ledger["leg_contracts"] if r["leg"] == "arena")
    assert row["steers"] == "arena"
    assert "arena" in authority.compute(ledger, {"leg:arena": {"verdict": "REJECTED"}})[
        "suspended"]
    assert "arena" not in authority.compute(ledger, {"leg:arena": {"verdict": "UNMEASURED"}})[
        "suspended"]
    assert tour.CONTESTANT_ORGAN["arena"] == "arena"


def test_the_champion_publishes_the_split_it_would_spend_today() -> None:
    days = {f"2026-09-{d:02d}": {"a": [10, 5], "b": [10, 1]} for d in range(1, 9)}
    split = pe.current_split({"rule": "posterior_mean", "prior": 2.0, "half_life_days": 7.0,
                              "explore_floor": 0.1}, days)
    assert split["a"] > split["b"] and abs(sum(split.values()) - 1.0) < 1e-9
    assert pe.current_split({"rule": "as_spent"}, days) == {}


def test_an_adopted_validator_takes_over_the_prejudge_screen(
        tmp_path: Path, monkeypatch: Any) -> None:
    """AC13 on the JUDGING side: the arena-adopted validator's expressible checks become
    pre-judge rules once they survive the sealed suite; inexpressible ones are refused."""
    monkeypatch.setattr(ts, "STATE", tmp_path)
    monkeypatch.setattr(ts, "NOW", NOW)
    monkeypatch.setattr(ts, "RATIFY_SUITE", ts.meta_benchmark.Suite(per_kind=1, n=120))
    genome = {**ts.meta_benchmark.ValidatorConfig().genome(),
              "extra": [["n", "<", -1.0], ["variants", ">", 1e9]]}
    out = ts._adopt_validator_screen(genome, ts.meta_benchmark.ValidatorConfig(), "rq_gen7")
    assert out["adopted"] == ["validator_arena:n<-1"]
    assert out["skipped"][0]["why"] == "feature not in SCREEN_FEATURES"
    from libs.tiers import prejudge_screen as pj
    rules = pj.active(pj.load_rules(tmp_path / pj.RULES.name))
    assert [r["source"] for r in rules] == ["validator_arena"]


# ------------------------------------------------------------------- the scheduler's consumer

def test_the_weights_reach_the_real_scheduler_and_never_cut(
        tmp_path: Path, monkeypatch: Any) -> None:
    _isolate_pricing(tmp_path, monkeypatch, None)
    base = cp.build_plan(dict(BASES))
    doc = {"generated_utc": datetime.now(UTC).isoformat(), "hour": "2026-10-06T12",
           "weights": {"leg0": 1.5, "judge0": 0.5}, "withdrawn": False}
    _isolate_pricing(tmp_path, monkeypatch, doc)
    steered = cp.build_plan(dict(BASES))
    b, s = base["legs"], steered["legs"]
    assert s["leg0"]["score"] > b["leg0"]["score"], "a weighted-up leg's price did not rise"
    assert s["judge0"]["score"] < b["judge0"]["score"], "a down-weighted judge leg did not fall"
    assert s["leg0"]["price_factor"] >= b["leg0"]["price_factor"]
    assert steered["order"].index("judge0") >= base["order"].index("judge0")
    assert all(v["planned_s"] >= v["base_s"] for v in s.values())
    assert steered["totals"]["never_reduced"]
    # what was APPLIED is logged for the tournament to credit, keyed by the steer hour
    rows = [json.loads(x) for x in
            (tmp_path / "steer_applied.jsonl").read_text("utf-8").splitlines()]
    assert rows[-1]["steer_hour"] == "2026-10-06T12"
    assert rows[-1]["weights"] == {"leg0": 1.5, "judge0": 0.5}


def test_a_short_pass_still_runs_every_generation_leg_it_ran_unsteered(
        tmp_path: Path, monkeypatch: Any) -> None:
    """hourly_cycle runs legs in `cycle_pricing.order` and the tail is what a short pass drops.
    Whatever the steer says, no generation leg may fall behind the cut it made unsteered: ups do
    not reorder, a 0.5 on a generation leg is floored, and only a judge leg may move later."""
    names = list(BASES)
    _isolate_pricing(tmp_path, monkeypatch, None)
    base = cp.build_plan(dict(BASES))
    doc = {"generated_utc": datetime.now(UTC).isoformat(), "hour": "h",
           "weights": {"leg5": 1.5, "leg4": 1.4, "leg0": 0.5, "deepen": 0.5, "judge0": 0.5,
                       "alpha_evolution": 0.5},
           "withdrawn": False}
    _isolate_pricing(tmp_path, monkeypatch, doc)
    steered = cp.build_plan(dict(BASES))
    o0, o1 = cp.order(names, base["legs"]), cp.order(names, steered["legs"])
    for cut in range(1, len(names)):
        ran0, ran1 = set(o0[:cut]), set(o1[:cut])
        gen_lost = {lg for lg in ran0 - ran1 if not lg.startswith("judge")}
        assert not gen_lost, f"a pass cut after {cut} legs drops generation leg(s) {gen_lost}"
    for leg in names:
        if not leg.startswith("judge"):
            assert steered["legs"][leg]["planned_s"] >= base["legs"][leg]["planned_s"]


def test_a_generation_leg_at_the_minimum_weight_keeps_its_slot_and_seconds(
        tmp_path: Path, monkeypatch: Any) -> None:
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
    warm = _warm({"researcher_market": {"gen": 0.5, "judge": 0.5, "other": 1.5}})
    doc2 = tour.steer({"researcher_market": {"gen": 0.5, "judge": 0.5, "other": 1.5}}, {},
                      warm, "h", down_ok=["judge"])
    assert doc2["legs"]["gen"]["due"] == 1.0 and doc2["legs"]["judge"]["due"] < 1.0


def test_the_market_is_no_longer_counted_twice(tmp_path: Path, monkeypatch: Any) -> None:
    _isolate_pricing(tmp_path, monkeypatch, None)
    monkeypatch.setattr(cp, "_researcher_prices", lambda: {"leg0": 9.0, "leg1": 1.0})
    plan = cp.build_plan(dict(BASES))
    assert all("researcher_market" not in v["priced_by"] for v in plan["legs"].values())
    assert plan["weights"]["researcher_market"] == 0.0


def test_a_withdrawn_or_stale_steer_moves_nothing(tmp_path: Path, monkeypatch: Any) -> None:
    _isolate_pricing(tmp_path, monkeypatch, {"generated_utc": datetime.now(UTC).isoformat(),
                                             "weights": {"leg0": 1.5}, "withdrawn": True})
    assert cp._steer_weights()[0] == {}
    old = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
    _isolate_pricing(tmp_path, monkeypatch, {"generated_utc": old, "weights": {"leg0": 1.5}})
    assert cp._steer_weights()[0] == {}


# --------------------------------------------------------------------------------------- I12

def test_a_contestant_needs_three_scored_hours_and_hedge_uses_its_rate() -> None:
    import math
    two = tour.authorities({"a": [0.9, 0.9], "b": [0.1, 0.1, 0.1]}, ["a", "b"])
    assert two["a"]["authority"] == 0.0 and two["a"]["status"] == "INSUFFICIENT_HOURS"
    assert two["b"]["authority"] == 1.0
    rows = tour.authorities({"a": [0.9] * 8, "b": [0.2] * 4}, ["a", "b"])
    assert rows["a"]["eta"] == round(math.sqrt(8 * math.log(2) / 8), 6)
    assert rows["a"]["authority"] > rows["b"]["authority"] > 0
    assert abs(rows["a"]["authority"] + rows["b"]["authority"] - 1.0) < 1e-6


def test_the_holdout_and_trial_are_seeded_random_slices() -> None:
    h1 = tour.holdout(LEGS20, "2026-10-06T12")
    assert h1 == tour.holdout(LEGS20, "2026-10-06T12"), "the draw is not reproducible"
    assert len(h1) == round(tour.HOLDOUT_SHARE * 20)
    assert any(tour.holdout(LEGS20, f"2026-10-06T{h:02d}") != h1 for h in range(13, 20))
    rest = sorted(set(LEGS20) - set(h1))
    assert tour.trial(rest, "2026-10-06T12", 4) != tour.trial(rest, "2026-10-06T13", 4) or \
        tour.trial(rest, "2026-10-06T14", 4) != tour.trial(rest, "2026-10-06T12", 4)


def test_an_inconclusive_test_runs_only_the_trial_slice_paid_by_the_judge() -> None:
    warm = _warm(ALT)
    doc = tour.steer(ALT, {}, warm, "h9", down_ok=LEGS20, now=NOW)
    assert doc["comparison"]["primary"] == "UNMEASURED"
    assert doc["mode"] == "TRIAL" and not doc["authoritative"] and not doc["withdrawn"]
    assert len(doc["trial"]) == len(doc["holdout"]) == 4
    moved = {lg for lg, w in doc["weights"].items() if w != 1.0}
    assert set(doc["trial"]) <= moved | {lg for lg in doc["trial"]
                                         if doc["legs"][lg]["applied"] == 1.0}
    assert not moved & set(doc["holdout"]), "a held-out leg ran on a weight"
    for lg in moved - set(doc["trial"]):
        assert doc["legs"][lg]["arm"] == "funding" and doc["weights"][lg] < 1.0
    assert doc["applied_mean"] == 1.0
    assert abs(sum(doc["weights"].values()) - len(doc["weights"])) < 1e-4


def test_inconclusive_with_no_authority_is_fully_neutral() -> None:
    doc = tour.steer(ALT, {}, [], "h9", down_ok=LEGS20, now=NOW)
    assert all(w == 1.0 for w in doc["weights"].values())
    assert all(r["authority"] == 0.0 for r in doc["contestants"].values())


def test_without_a_judge_leg_to_pay_nothing_moves_up() -> None:
    doc = tour.steer({"researcher_market": dict.fromkeys(LEGS20[:10], 1.4) |
                      dict.fromkeys(LEGS20[10:], 1.0)}, {},
                     _warm({"researcher_market": dict.fromkeys(LEGS20[:10], 1.4)}),
                     "h9", down_ok=[], now=NOW)
    assert all(w == 1.0 for w in doc["weights"].values())


def _block_hist(treated: float, holdout: float, n: int, t0: datetime) -> list[dict[str, Any]]:
    return [{"at": (t0 + timedelta(hours=h)).isoformat(),
             "outcomes": {"a": treated + 0.01 * h, "b": holdout + 0.01 * h},
             "legs": {"a": {"due": 1.3, "applied": 1.3, "arm": "trial"},
                      "b": {"due": 1.3, "applied": 1.0, "arm": "holdout"}}}
            for h in range(n)]


def test_arms_are_classified_by_the_applied_weight() -> None:
    hist = [{"at": NOW.isoformat(), "outcomes": {"a": 9.0, "b": 1.0, "c": 5.0},
             "legs": {"a": {"due": 1.3, "applied": 1.0, "arm": "trial"},      # never applied
                      "b": {"due": 1.3, "applied": 1.0, "arm": "holdout"},
                      "c": {"due": 1.3, "applied": 1.3, "arm": "treated"}}}]
    bl = tour.blocks(hist)
    assert bl == [{"at": NOW.isoformat(), "d": 4.0, "n_treated": 1, "n_holdout": 1}]


def test_the_sequential_test_is_inconclusive_until_the_evidence_accumulates() -> None:
    assert tour.sequential_test([1.0, 1.0])["verdict"] == "UNMEASURED"
    noise = [(-1) ** h * 1.0 for h in range(40)]
    assert tour.sequential_test(noise)["verdict"] == "UNDECIDED"
    assert tour.sequential_test([2.0] * 30)["verdict"] == "ADMITTED"
    assert tour.sequential_test([-2.0] * 30)["verdict"] == "REJECTED"


def test_the_trial_slice_turns_unmeasured_into_admitted() -> None:
    """From no history the trial slice produces treated-vs-holdout blocks, and when the desk
    responds to the weights the test moves UNMEASURED -> ADMITTED; then every non-holdout leg is
    treated."""
    hist: list[dict[str, Any]] = _warm(ALT, start=NOW - timedelta(hours=10))
    modes = []
    t0 = NOW
    doc: dict[str, Any] = {}
    for h in range(80):
        now = t0 + timedelta(hours=h)
        doc = tour.steer(ALT, {}, hist, f"h{h}", down_ok=LEGS20, now=now)
        modes.append((doc["mode"], doc["comparison"]["primary"]))
        if doc["mode"] == "ADMITTED":
            break
        outcomes = {lg: (10.0 if r["applied"] > 1.0 else 2.0) + 0.1 * ((h + i) % 3)
                    for i, (lg, r) in enumerate(doc["legs"].items())}
        hist.append({"at": now.isoformat(), "tilts": ALT,
                     "legs": {lg: {k: r[k] for k in ("due", "applied", "arm")}
                              for lg, r in doc["legs"].items()},
                     "outcomes": outcomes})
    assert modes[0] == ("TRIAL", "UNMEASURED")
    assert doc["mode"] == "ADMITTED" and doc["authoritative"], modes[-3:]
    assert doc["comparison"]["up"]["blocks"] >= tour.MIN_BLOCKS
    treated = [lg for lg, r in doc["legs"].items() if r["arm"] == "treated"]
    assert treated and not set(treated) & set(doc["holdout"])


def test_a_rejected_test_is_neutral_cools_down_then_retries() -> None:
    t0 = NOW
    hist = _block_hist(1.0, 9.0, 30, t0 - timedelta(hours=40))
    hist += _warm(ALT, start=t0 - timedelta(hours=8))
    doc = tour.steer(ALT, {}, hist, "h0", down_ok=LEGS20, now=t0)
    assert doc["comparison"]["up"]["verdict"] == "REJECTED" and doc["mode"] == "REJECTED"
    assert doc["withdrawn"] and set(doc["weights"].values()) == {1.0}
    assert doc["rejected_at"] == t0.isoformat()
    cool = tour.steer(ALT, {}, hist, "h1", down_ok=LEGS20, rejected_at=doc["rejected_at"],
                      now=t0 + timedelta(hours=1))
    assert cool["mode"] == "COOLDOWN" and set(cool["weights"].values()) == {1.0}
    later = t0 + timedelta(hours=tour.COOLDOWN_H + 1)
    hist2 = hist + _warm(ALT, start=t0 + timedelta(hours=2))
    retry = tour.steer(ALT, {}, hist2, "h99", down_ok=LEGS20, rejected_at=doc["rejected_at"],
                       now=later)
    assert retry["mode"] == "TRIAL" and retry["comparison"]["primary"] == "UNMEASURED"
    assert any(w != 1.0 for w in retry["weights"].values())


def test_forward_pnl_is_a_scored_channel_that_moves_authority() -> None:
    """I12's P&L link: the change in each leg's forward R is scored like births; a contestant that
    points at the legs whose certificates then earned forward R gains authority on it alone."""
    hist = []
    for h in range(5):
        hist.append({"at": (NOW - timedelta(hours=10 - h)).isoformat(), "legs": {},
                     "tilts": {"arena": {"x": 1.3}, "researcher_market": {"y": 1.3}},
                     "pnl_outcomes": {"x": 2.0 + 0.01 * h, "y": -1.0, "z": 0.0}})
    rows = tour.authorities(tour.hour_gains(hist), ["arena", "researcher_market"])
    assert rows["arena"]["authority"] > rows["researcher_market"]["authority"]
    cmp_ = tour.holdout_comparison(hist)
    assert "forward_r" in cmp_ and "elogw" in cmp_


def test_weights_are_bounded() -> None:
    w = tour.combine({"a": {"x": 1.5, "y": 0.5, "z": 1.5}}, {"a": 1.0})
    assert all(0.5 <= v <= 1.5 for v in w.values())
    zs = tour.zero_sum({"x": 1.5, "y": 0.8}, funders=["j1", "j2"])
    assert abs(sum(zs.values()) - len(zs)) < 1e-6 and zs["j1"] < 1.0


# ------------------------------------------------------------------------- outcome scoring

def _score_run(tmp_path: Path, monkeypatch: Any, families: list[str], *, prior: int = 0,
               cpu_rows: list[tuple[int, str, float]] | None = None,
               applied_log: bool = True) -> dict[str, Any]:
    sub = tmp_path / f"run{len(list(tmp_path.iterdir()))}"
    sub.mkdir()
    _isolate_tier_s(sub, monkeypatch, arena=_arena({"mutate_survivor": "LEADS"}))
    t0 = NOW - timedelta(hours=2)
    _seed_state(sub, [{"hour": "old", "at": t0.isoformat(), "outcomes": None,
                       "legs": {"alpha_evolution": {"due": 1.1, "applied": 1.1, "arm": "trial"},
                                "deepen": {"due": 1.1, "applied": 1.0, "arm": "holdout"}},
                       "tilts": {}}])
    if applied_log:
        ts.STEER_APPLIED.write_text(json.dumps({"at": (t0 + timedelta(minutes=5)).isoformat(),
                                                "steer_hour": "old",
                                                "weights": {"alpha_evolution": 1.1}}) + "\n",
                                    encoding="utf-8")
    (sub / "state" / "researcher_prices.json").write_text(json.dumps({
        "generated_utc": NOW.isoformat(),
        "researchers": {"miner:alpha_evolution": {"leg": "alpha_evolution"}}}), encoding="utf-8")
    rows = [{"at": (t0 - timedelta(hours=5)).isoformat(), "source": "miner:other",
             "symbol": "EURUSD", "family": families[0], "fate": "BORN"}] * prior
    rows += [{"at": (t0 + timedelta(minutes=10 + i)).isoformat(),
              "source": "miner:alpha_evolution", "symbol": "EURUSD", "family": f,
              "fate": "BORN"} for i, f in enumerate(families)]
    ts.HGRAPH.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    cpu = cpu_rows if cpu_rows is not None else [(30, "alpha_evolution", 1800.0)]
    ts.COMPUTE.write_text("".join(json.dumps({"at": (t0 + timedelta(minutes=m)).isoformat(),
                                              "run": run, "cpu_s": c}) + "\n"
                                  for m, run, c in cpu), encoding="utf-8")
    ts.organ_steer()
    st = json.loads((sub / "state" / "scheduler_steer.json").read_text("utf-8"))
    return next(a for a in st["assignments"] if a["hour"] == "old")


def test_births_are_unique_pairs_novelty_deflated(tmp_path: Path, monkeypatch: Any) -> None:
    distinct = _score_run(tmp_path, monkeypatch, ["f1", "f2", "f3"])["outcomes"]
    dupes = _score_run(tmp_path, monkeypatch, ["f1", "f1", "f1"])["outcomes"]
    single = _score_run(tmp_path, monkeypatch, ["f1"])["outcomes"]
    assert distinct["alpha_evolution"] == 6.0           # 3 new pairs in half a CPU-hour
    assert dupes["alpha_evolution"] == single["alpha_evolution"] == 2.0, \
        "duplicates of one pair in the hour raised the score"
    old = _score_run(tmp_path, monkeypatch, ["f1"], prior=3)["outcomes"]
    assert old["alpha_evolution"] == 1.0                # 1/sqrt(1 + 3) per pair, per 0.5 h


def test_a_lost_run_scores_as_harm(tmp_path: Path, monkeypatch: Any) -> None:
    """deepen ran in each of the six hours before the window and burned nothing in it."""
    cpu = [(30, "alpha_evolution", 1800.0)] + [(-60 * k + 10, "deepen", 300.0)
                                               for k in range(1, 7)]
    a = _score_run(tmp_path, monkeypatch, ["f1", "f2", "f3"], cpu_rows=cpu)
    assert a["lost_runs"] == ["deepen"]
    assert a["outcomes"]["deepen"] < 0


def test_outcomes_are_credited_to_the_weights_actually_applied(
        tmp_path: Path, monkeypatch: Any) -> None:
    spent = _score_run(tmp_path, monkeypatch, ["f1"])
    assert spent["applied_from"] == "cycle_pricing"
    assert spent["legs"]["alpha_evolution"]["applied"] == 1.1
    never = _score_run(tmp_path, monkeypatch, ["f1"], applied_log=False)
    assert never["applied_from"] == "never_spent"
    assert never["legs"]["alpha_evolution"]["applied"] == 1.0, \
        "a plan cycle_pricing never spent was credited as treated"
